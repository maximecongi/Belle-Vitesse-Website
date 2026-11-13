"""Devis de la timeline commerciale : montant HT et fichier sur « Devis envoyé » (1_DEVIS kDrive), indicateurs, MCP."""
import base64
import io
import os
import tempfile
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from models import Project, ProjectCommercialEvent, db
from services.admin.commercial_timeline import (
    add_commercial_event,
    build_commercial_timeline,
    delete_commercial_event,
    pending_quotes_summary,
    reference_quote_amount,
    update_commercial_event,
)
from services.admin.indicators import commercial_indicators, last_12_months, resolve_period
from services.common.kdrive.paths import build_document_directory_path
from tests.base import BaseTestCase

NOW = datetime(2026, 11, 12, 15, 0)
PDF = b"%PDF-1.4 devis test"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 10
SYNC = "services.common.kdrive.tasks.dispatch_sync_quote_file"


class _OutputMixin:
    """OUTPUT_FOLDER temporaire et synchronisation kDrive simulée."""

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = self._tmp.name
        self._cfg = patch.dict(self.app.config, {"OUTPUT_FOLDER": self.tmp})
        self._cfg.start()
        self._sync = patch(SYNC)
        self.sync = self._sync.start()

    def tearDown(self):
        self._sync.stop()
        self._cfg.stop()
        self._tmp.cleanup()
        super().tearDown()

    def local(self, event):
        return os.path.join(self.tmp, event.file_path)


class QuoteServiceTest(_OutputMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.prod = self.create_production("Prod Devis")
        self.project = Project(name="Pub Devis", production_id=self.prod.id)
        db.session.add(self.project)
        db.session.commit()

    def _add(self, event_type="quote_sent", day="2026-11-02", **kw):
        return add_commercial_event(self.project.id, event_type=event_type, date_str=day, now=NOW, **kw)

    def _update(self, event, **kw):
        values = {"event_type": event.event_type, "date_str": event.occurred_at.date().isoformat(), "now": NOW}
        values.update(kw)
        return update_commercial_event(self.project.id, event.id, **values)

    def test_kdrive_folder_is_flat_1_devis(self):
        self.assertEqual(build_document_directory_path(self.project, "quote", "DEVIS-1"), "1_DEVIS")

    def test_quote_without_amount_nor_file(self):
        ev = self._add()
        self.assertIsNone(ev.quote_amount)
        self.assertIsNone(ev.file_path)
        self.sync.assert_not_called()

    def test_amount_parsed_and_ignored_on_other_types(self):
        ev = self._add(quote_amount="4 850,50 €")
        self.assertEqual(ev.quote_amount, Decimal("4850.50"))
        self.assertEqual(self._add("email_out", quote_amount="1000").quote_amount, None)
        with self.assertRaises(ValueError):
            self._add(quote_amount="abc")
        db.session.rollback()
        with self.assertRaises(ValueError):
            self._add(quote_amount="-5")

    def test_file_stored_synced_replaced_and_removed(self):
        ev = self._add(quote_amount="1200", quote_file=("Devis 2026-142.pdf", PDF))
        self.assertEqual(ev.file_name, "Devis 2026-142.pdf")
        self.assertTrue(ev.file_path.startswith(f"DEVIS/{self.project.id}/{ev.id}_"))
        with open(self.local(ev), "rb") as fh:
            self.assertEqual(fh.read(), PDF)
        self.sync.assert_called_once_with(self.project.id, f"DEVIS-{ev.id}", ev.file_path, "Devis 2026-142.pdf")

        # Remplacement : l'ancienne copie disparaît, le montant vide est retiré
        old = self.local(ev)
        self.sync.reset_mock()
        ev = self._update(ev, quote_file=("scan.png", PNG), quote_amount="")
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.exists(self.local(ev)))
        self.assertIsNone(ev.quote_amount)
        self.sync.assert_called_once_with(self.project.id, f"DEVIS-{ev.id}", ev.file_path, "scan.png")

        # Modification sans fichier : le fichier est conservé, pas de synchro
        self.sync.reset_mock()
        ev = self._update(ev, summary="v2")
        self.assertEqual(ev.file_name, "scan.png")
        self.sync.assert_not_called()

        # Retrait
        path = self.local(ev)
        ev = self._update(ev, remove_quote_file="1")
        self.assertIsNone(ev.file_path)
        self.assertFalse(os.path.exists(path))
        self.sync.assert_called_once_with(self.project.id, f"DEVIS-{ev.id}", None, None)

    def test_invalid_files_rejected_before_saving(self):
        for name, content, msg in (("devis.exe", PDF, "Format"), ("devis.png", PDF, "PNG"),
                                   ("devis.pdf", b"", "vide")):
            with self.assertRaisesRegex(ValueError, msg):
                self._add(quote_file=(name, content))
        self.assertEqual(ProjectCommercialEvent.query.count(), 0)
        self.sync.assert_not_called()

    def test_type_change_drops_quote_data(self):
        ev = self._add(quote_amount="900", quote_file=("d.pdf", PDF))
        path = self.local(ev)
        ev = self._update(ev, event_type="email_out")
        self.assertIsNone(ev.quote_amount)
        self.assertIsNone(ev.file_path)
        self.assertFalse(os.path.exists(path))

    def test_delete_removes_file(self):
        ev = self._add(quote_file=("d.pdf", PDF))
        path, entity = self.local(ev), ev.kdrive_entity_id
        self.sync.reset_mock()
        delete_commercial_event(self.project.id, ev.id)
        self.assertFalse(os.path.exists(path))
        self.sync.assert_called_once_with(self.project.id, entity, None, None)

    def test_reference_quote_is_latest_with_amount(self):
        self._add(day="2026-10-01", quote_amount="5000")
        self._add(day="2026-10-10", quote_amount="4200")   # devis révisé : remplace le précédent
        self._add(day="2026-10-20")                         # sans montant : ignoré
        events = self.project.commercial_events
        self.assertEqual(reference_quote_amount(events), 4200.0)
        self.assertEqual(reference_quote_amount(events, until=datetime(2026, 10, 5)), 5000.0)
        summary = pending_quotes_summary([self.project])
        self.assertEqual((summary["count"], summary["amount"], summary["without_amount"]), (1, 4200.0, 0))

    def test_timeline_edit_payload(self):
        ev = self._add(quote_amount="1250.5", quote_file=("d.pdf", PDF))
        tl = build_commercial_timeline(self.project, now=NOW)
        item = next(i for i in tl["events"] if i["id"] == ev.id)
        self.assertEqual(item["quote_file_name"], "d.pdf")
        self.assertEqual((item["edit"]["quote_amount"], item["edit"]["quote_file_name"]), ("1250.50", "d.pdf"))
        self.assertEqual(tl["quote_types"], ["quote_sent"])


class QuoteRoutesTest(_OutputMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.commercial = self.create_user(firstname="Carla", lastname="Com", mail="carla.q@bv.fr", role="Commercial")
        self.tech = self.create_user(firstname="Tina", lastname="Tech", mail="tina.q@bv.fr", role="Technicien")
        prod = self.create_production("Prod Devis Routes")
        self.project = Project(name="Tournage Devis", production_id=prod.id)
        db.session.add(self.project)
        db.session.commit()

    def _login(self, user):
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = user.id
            sess["admin_user_role"] = user.role

    def test_upload_download_and_remove(self):
        self._login(self.commercial)
        base = f"/admin/projects/{self.project.id}/commercial-events"
        resp = self.client.post(base, data={
            "event_type": "quote_sent", "occurred_date": date.today().isoformat(), "quote_amount": "3 000",
            "quote_file": (io.BytesIO(PDF), "Devis-BV.pdf"),
        }, content_type="multipart/form-data", headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(resp.status_code, 201, resp.get_json())
        ev = ProjectCommercialEvent.query.one()
        self.assertEqual((ev.quote_amount, ev.file_name), (Decimal("3000.00"), "Devis-BV.pdf"))
        self.assertIn("Devis-BV.pdf", resp.get_json()["html"])
        self.assertIn(f"{base}/{ev.id}/quote-file", resp.get_json()["html"])

        dl = self.client.get(f"{base}/{ev.id}/quote-file")
        self.assertEqual(dl.status_code, 200)
        self.assertEqual(dl.data, PDF)
        self.assertIn("Devis-BV.pdf", dl.headers["Content-Disposition"])
        dl.close()

        resp = self.client.post(f"{base}/{ev.id}/edit", data={
            "event_type": "quote_sent", "occurred_date": date.today().isoformat(), "quote_amount": "3000",
            "remove_quote_file": "1",
        }, headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(resp.status_code, 200, resp.get_json())
        db.session.expire_all()
        self.assertIsNone(db.session.get(ProjectCommercialEvent, ev.id).file_path)
        self.assertEqual(self.client.get(f"{base}/{ev.id}/quote-file").status_code, 404)

    def test_bad_file_returns_error(self):
        self._login(self.commercial)
        resp = self.client.post(f"/admin/projects/{self.project.id}/commercial-events", data={
            "event_type": "quote_sent", "occurred_date": date.today().isoformat(),
            "quote_file": (io.BytesIO(b"MZ..."), "devis.pdf"),
        }, content_type="multipart/form-data", headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("PDF", resp.get_json()["message"])
        self.assertEqual(ProjectCommercialEvent.query.count(), 0)

    def test_technician_cannot_download(self):
        ev = add_commercial_event(self.project.id, event_type="quote_sent", date_str="2026-11-02", now=NOW,
                                  quote_file=("d.pdf", PDF))
        self._login(self.tech)
        resp = self.client.get(f"/admin/projects/{self.project.id}/commercial-events/{ev.id}/quote-file")
        self.assertIn(resp.status_code, (302, 403, 404))
        self.assertNotEqual(resp.data, PDF)


class QuoteIndicatorsTest(_OutputMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.prod = self.create_production("Prod Devis Indicateurs")

    def _project(self, name, events):
        p = Project(name=name, production_id=self.prod.id)
        db.session.add(p)
        db.session.commit()
        for ev_type, day, extra in events:
            add_commercial_event(p.id, event_type=ev_type, date_str=day, **{"now": NOW, **extra})
        return p

    def test_quote_amounts(self):
        # A : devis révisé puis confirmé ; B : abandonné ; C : en attente ; D : en attente sans montant
        self._project("A", [("quote_sent", "2026-10-20", {"quote_amount": "5000"}),
                            ("quote_sent", "2026-10-25", {"quote_amount": "4000"}),
                            ("confirmed", "2026-10-30", {})])
        self._project("B", [("quote_sent", "2026-10-22", {"quote_amount": "1000"}),
                            ("lost", "2026-11-02", {"lost_reason": "price"})])
        self._project("C", [("quote_sent", "2026-11-05", {"quote_amount": "2500"})])
        self._project("D", [("quote_sent", "2026-11-06", {})])

        period = resolve_period("30d", NOW.date())
        c = commercial_indicators(period, last_12_months(period), now=NOW)
        self.assertEqual((c["quoted_amount"], c["quoted_count"]), (7500.0, 3))  # A compte une fois (4000)
        self.assertEqual((c["won_amount"], c["lost_amount"]), (4000.0, 1000.0))
        self.assertEqual(c["value_conversion_rate"], 80)
        pq = c["pending_quotes"]
        self.assertEqual((pq["count"], pq["amount"], pq["without_amount"]), (2, 2500.0, 1))
        self.assertEqual([r["key"] for r in c["quotes"]["rows"]], ["quoted", "won", "lost"])
        self.assertTrue(c["quotes"]["has_data"])

    def test_indicators_page_renders_quote_amounts(self):
        today = date.today().isoformat()
        self._project("P", [("quote_sent", today, {"quote_amount": "12500", "now": datetime.now()})])
        with self.client.session_transaction() as sess:
            sess["admin_authenticated"] = True
            sess["admin_user_id"] = 1
            sess["admin_user_role"] = "Administrateur"
        html = self.client.get("/admin/indicators?tab=commercial&period=30d").get_data(as_text=True)
        self.assertIn("Devis en attente", html)
        self.assertIn("12 500 €", html)
        self.assertIn("Devis · montants HT", html)
        self.assertIn("Transformation en valeur", html)


class QuoteMcpToolsTest(_OutputMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        from mcp_auth.auth import McpUserContext
        from mcp_server.context import CURRENT_MCP_USER
        self.manager = self.create_user(firstname="Marc", lastname="Mgr", mail="marc.q@bv.fr", role="Manager")
        prod = self.create_production("Prod Devis MCP")
        self.project = Project(name="Pub Devis MCP", production_id=prod.id)
        db.session.add(self.project)
        db.session.commit()
        self.ctx = CURRENT_MCP_USER
        self.ctx.set(McpUserContext(self.manager.id, "marc.q@bv.fr", "Marc", "Mgr", "manager", scope="write"))

    def tearDown(self):
        self.ctx.set(None)
        super().tearDown()

    def test_amount_and_file_cycle(self):
        from mcp_server.tools import commercial as tools

        res = tools.add_commercial_event(self.project.id, "quote_sent", "2026-11-01", quote_amount=4850)
        self.assertEqual(res["status"], "success", res)
        self.assertEqual(res["event"]["quote_amount"], 4850.0)
        event_id = res["event"]["id"]

        # Montant conservé si non fourni, retiré avec 0
        self.assertEqual(tools.update_commercial_event(event_id, summary="v2")["event"]["quote_amount"], 4850.0)
        self.assertIsNone(tools.update_commercial_event(event_id, quote_amount=0)["event"]["quote_amount"])

        ok64 = base64.b64encode(PDF).decode()
        self.assertIn("base64", tools.attach_commercial_quote_file(event_id, "d.pdf", "%%%")["message"])
        res = tools.attach_commercial_quote_file(event_id, "Devis.pdf", "data:application/pdf;base64," + ok64)
        self.assertEqual(res["status"], "success", res)
        self.assertEqual((res["event"]["quote_file_name"], res["kdrive_folder"]), ("Devis.pdf", "1_DEVIS"))
        self.sync.assert_called_once()

        # Fichier refusé sur un autre type d'événement
        other = tools.add_commercial_event(self.project.id, "email_out", "2026-11-02")["event"]["id"]
        self.assertEqual(tools.attach_commercial_quote_file(other, "d.pdf", ok64)["status"], "error")

        self.assertEqual(tools.remove_commercial_quote_file(event_id)["status"], "confirmation_required")
        res = tools.remove_commercial_quote_file(event_id, confirm=True)
        self.assertEqual(res["status"], "success", res)
        self.assertIsNone(res["event"]["quote_file_name"])

        stats = tools.get_commercial_stats()
        self.assertIn("quotes_pending_amount", stats)
