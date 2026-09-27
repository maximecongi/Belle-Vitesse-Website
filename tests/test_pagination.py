import unittest
from flask import Flask
from utils.pagination import Pagination


class TestPagination(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        self.app.config["SERVER_NAME"] = "localhost"

        @self.app.route("/admin/projects")
        def admin_projects_list():
            return "ok"

    def test_empty_pagination(self):
        p = Pagination(items=[], page=1, per_page=25, total=0)
        self.assertEqual(p.page, 1)
        self.assertEqual(p.pages, 1)
        self.assertEqual(p.total, 0)
        self.assertEqual(p.start_index, 0)
        self.assertEqual(p.end_index, 0)
        self.assertFalse(p.has_prev)
        self.assertFalse(p.has_next)
        self.assertIsNone(p.prev_num)
        self.assertIsNone(p.next_num)
        self.assertEqual(list(p.iter_pages()), [1])

    def test_single_page(self):
        p = Pagination(items=list(range(10)), page=1, per_page=25, total=10)
        self.assertEqual(p.pages, 1)
        self.assertEqual(p.start_index, 1)
        self.assertEqual(p.end_index, 10)
        self.assertFalse(p.has_prev)
        self.assertFalse(p.has_next)

    def test_multi_pages_middle(self):
        p = Pagination(items=list(range(20)), page=3, per_page=20, total=75)
        self.assertEqual(p.pages, 4)
        self.assertEqual(p.start_index, 41)
        self.assertEqual(p.end_index, 60)
        self.assertTrue(p.has_prev)
        self.assertTrue(p.has_next)
        self.assertEqual(p.prev_num, 2)
        self.assertEqual(p.next_num, 4)

    def test_multi_pages_last(self):
        p = Pagination(items=list(range(15)), page=4, per_page=20, total=75)
        self.assertEqual(p.pages, 4)
        self.assertEqual(p.start_index, 61)
        self.assertEqual(p.end_index, 75)
        self.assertTrue(p.has_prev)
        self.assertFalse(p.has_next)
        self.assertEqual(p.prev_num, 3)
        self.assertIsNone(p.next_num)

    def test_iter_pages_with_gaps(self):
        p = Pagination(items=[], page=10, per_page=10, total=200)  # 20 pages
        pages = list(p.iter_pages(left_edge=2, left_current=2, right_current=2, right_edge=2))
        # Expected: [1, 2, None, 8, 9, 10, 11, 12, None, 19, 20]
        self.assertEqual(pages, [1, 2, None, 8, 9, 10, 11, 12, None, 19, 20])

    def test_url_for_page_preserves_query_params(self):
        with self.app.test_request_context("/admin/projects?q=test&status=upcoming&page=1"):
            p = Pagination(items=[], page=1, per_page=25, total=50)
            url_page_2 = p.url_for_page(2)
            self.assertIn("page=2", url_page_2)
            self.assertIn("q=test", url_page_2)
            self.assertIn("status=upcoming", url_page_2)


if __name__ == "__main__":
    unittest.main()
