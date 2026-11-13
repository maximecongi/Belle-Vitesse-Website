"""Outils MCP de facturation : factures d'un projet (lecture / ajout / modification / suppression) et CA."""
from unittest.mock import patch

from models import Project, ProjectInvoice, Vehicle, db
from tests.base import BaseTestCase


class InvoiceMcpToolsTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        from mcp_auth.auth import McpUserContext
        from mcp_server.context import CURRENT_MCP_USER
        self.manager = self.create_user(firstname="Marc", lastname="Mgr", mail="marc.inv@bv.fr", role="Manager")
        self.prod = self.create_production("Prod Factures MCP")
        db.session.add_all([
            Vehicle(id="rec_inv_erover", fields={"name": "eRover"}, display_order=0),
            Vehicle(id="rec_inv_erider", fields={"name": "eRider"}, display_order=1),
        ])
        self.project = Project(name="Pub Factures", production_id=self.prod.id,
                               vehicles_to_check="rec_inv_erover,rec_inv_erider")
        db.session.add(self.project)
        db.session.commit()
        self.ctx = CURRENT_MCP_USER
        self.ctx.set(McpUserContext(self.manager.id, "marc.inv@bv.fr", "Marc", "Mgr", "manager", scope="write"))

    def tearDown(self):
        self.ctx.set(None)
        super().tearDown()

    def test_full_cycle(self):
        from mcp_server.tools import invoices as tools
        from mcp_server.tools import projects

        # Ajout : ventilation par nom ou par id, le reste forme les autres prestations
        res = tools.add_project_invoice(self.project.project_id, "09/11/2026", 7588, number="F-2026-11-1",
                                        label="Semaine 2", equipment={"eRover": 3500, "rec_inv_erider": 2205})
        self.assertEqual(res["status"], "success", res)
        inv = res["invoice"]
        self.assertEqual((inv["issued_on"], inv["amount"], inv["equipment_total"], inv["other"]),
                         ("2026-11-09", 7588.0, 5705.0, 1883.0))
        self.assertEqual({e["name"]: e["amount"] for e in inv["equipment"]}, {"eRover": 3500.0, "eRider": 2205.0})
        self.assertFalse(inv["is_paid"])

        # Refus : matériel non engagé, matériel > montant, date manquante
        bad = tools.add_project_invoice(self.project.id, "2026-11-09", 100, equipment={"Jackal": 50})
        self.assertEqual(bad["status"], "error")
        self.assertIn("non engagé", bad["message"])
        bad = tools.add_project_invoice(self.project.id, "2026-11-09", 100, equipment={"eRover": 500})
        self.assertIn("dépasse", bad["message"])
        bad = tools.add_project_invoice(self.project.id, "", 100)
        self.assertEqual(bad["status"], "error")
        self.assertEqual(ProjectInvoice.query.count(), 1)

        # Modification partielle et passage en payée
        res = tools.update_project_invoice(inv["id"], is_paid=True, paid_on="2026-11-20")
        self.assertEqual(res["status"], "success", res)
        self.assertEqual((res["invoice"]["is_paid"], res["invoice"]["paid_on"]), (True, "2026-11-20"))
        self.assertEqual(res["invoice"]["number"], "F-2026-11-1")  # inchangé
        res = tools.update_project_invoice(inv["id"], amount=6000, equipment={})
        self.assertEqual((res["invoice"]["amount"], res["invoice"]["other"], res["invoice"]["equipment"]),
                         (6000.0, 6000.0, []))
        self.assertTrue(res["invoice"]["is_paid"])
        self.assertEqual(tools.update_project_invoice(inv["id"], amount=-5)["status"], "error")

        # Lecture : projet et fiche projet
        tools.add_project_invoice(self.project.id, "2026-11-16", 1000, label="Semaine 3")
        listing = tools.get_project_invoices(self.project.id)
        self.assertEqual([i["label"] for i in listing["invoices"]], ["Semaine 2", "Semaine 3"])
        self.assertEqual(listing["totals"], {"count": 2, "total": 7000.0, "paid": 6000.0, "due": 1000.0,
                                             "paid_rate": 86})
        self.assertEqual(projects.get_project(self.project.id)["billing"]["totals"]["total"], 7000.0)

        # Suppression avec confirmation
        self.assertEqual(tools.delete_project_invoice(inv["id"])["status"], "confirmation_required")
        with patch("services.common.kdrive.tasks.dispatch_sync_invoice_file") as sync:
            self.assertEqual(tools.delete_project_invoice(inv["id"], confirm=True)["status"], "success")
            sync.assert_not_called()  # pas de fichier joint
        self.assertEqual(ProjectInvoice.query.count(), 1)

    def test_revenue_stats(self):
        from mcp_server.tools import invoices as tools

        tools.add_project_invoice(self.project.id, "2026-10-05", 5000, equipment={"eRover": 4000}, is_paid=True)
        tools.add_project_invoice(self.project.id, "2026-11-02", 3000, equipment={"eRider": 1000})
        tools.add_project_invoice(self.project.id, "2025-11-02", 999)  # hors bornes
        res = tools.get_revenue_stats(start_date="2026-10-01", end_date="2026-11-30")
        self.assertEqual(res["status"], "success", res)
        self.assertEqual((res["count"], res["total"], res["paid"], res["due"], res["projects_count"]),
                         (2, 8000.0, 5000.0, 3000.0, 1))
        self.assertEqual([(r["name"], r["amount"]) for r in res["by_equipment"]], [("eRover", 4000.0), ("eRider", 1000.0)])
        self.assertEqual((res["equipment_total"], res["other_total"]), (5000.0, 3000.0))
        self.assertEqual(res["by_month"], [{"month": "2026-10", "amount": 5000.0}, {"month": "2026-11", "amount": 3000.0}])

        self.assertEqual(tools.get_revenue_stats(start_date="2026-12-01", end_date="2026-11-01")["status"], "error")
        rolling = tools.get_revenue_stats(period="12m")
        self.assertEqual(rolling["status"], "success")
        self.assertIn("previous", rolling)

    def test_attach_and_remove_file(self):
        import base64
        import os
        import tempfile
        from mcp_server.tools import invoices as tools

        inv_id = tools.add_project_invoice(self.project.id, "2026-11-09", 1200, number="F-2026-11-1")["invoice"]["id"]
        pdf = b"%PDF-1.4 facture test"
        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict(self.app.config, {"OUTPUT_FOLDER": tmp}), \
                patch("services.common.kdrive.tasks.dispatch_sync_invoice_file") as sync:
            # Refus : base64 invalide, extension, contenu ne correspondant pas à l'extension
            self.assertIn("base64", tools.attach_project_invoice_file(inv_id, "f.pdf", "%%%")["message"])
            ok64 = base64.b64encode(pdf).decode()
            self.assertIn("Format", tools.attach_project_invoice_file(inv_id, "f.exe", ok64)["message"])
            self.assertIn("PNG", tools.attach_project_invoice_file(inv_id, "f.png", ok64)["message"])
            sync.assert_not_called()

            # Dépôt (préfixe data: accepté) : copie locale, envoi kDrive dans 2_FACTURES
            res = tools.attach_project_invoice_file(inv_id, "F-2026-11-1.pdf", "data:application/pdf;base64," + ok64)
            self.assertEqual(res["status"], "success", res)
            self.assertEqual((res["invoice"]["file_name"], res["invoice"]["has_file"], res["replaced_file"]),
                             ("F-2026-11-1.pdf", True, None))
            invoice = db.session.get(ProjectInvoice, inv_id)
            local = os.path.join(tmp, invoice.file_path)
            with open(local, "rb") as fh:
                self.assertEqual(fh.read(), pdf)
            sync.assert_called_once_with(self.project.id, f"FACT-{inv_id}", invoice.file_path, "F-2026-11-1.pdf")

            # Remplacement : l'ancienne copie disparaît
            png = b"\x89PNG\r\n\x1a\n" + b"0" * 10
            res = tools.attach_project_invoice_file(inv_id, "scan.png", base64.b64encode(png).decode())
            self.assertEqual(res["replaced_file"], "F-2026-11-1.pdf")
            self.assertFalse(os.path.exists(local))
            db.session.expire_all()
            invoice = db.session.get(ProjectInvoice, inv_id)
            self.assertTrue(invoice.file_path.endswith("_scan.png"))
            local = os.path.join(tmp, invoice.file_path)
            self.assertTrue(os.path.exists(local))

            # Retrait avec confirmation
            self.assertEqual(tools.remove_project_invoice_file(inv_id)["status"], "confirmation_required")
            sync.reset_mock()
            res = tools.remove_project_invoice_file(inv_id, confirm=True)
            self.assertEqual(res["status"], "success", res)
            self.assertFalse(res["invoice"]["has_file"])
            self.assertFalse(os.path.exists(local))
            sync.assert_called_once_with(self.project.id, f"FACT-{inv_id}", None, None)
            self.assertEqual(tools.remove_project_invoice_file(inv_id, confirm=True)["status"], "error")

    def test_read_only_scope_cannot_write(self):
        from mcp_auth.auth import McpUserContext
        from mcp_server.tools import invoices as tools

        self.ctx.set(McpUserContext(self.manager.id, "marc.inv@bv.fr", "Marc", "Mgr", "manager", scope="read_only"))
        res = tools.add_project_invoice(self.project.id, "2026-11-09", 100)
        self.assertEqual(res.get("error_code"), 403)
        self.assertEqual(tools.get_project_invoices(self.project.id)["status"], "success")
