import unittest

from app import TASKS, render_page


class TaskBoardTests(unittest.TestCase):
    def test_seed_lists_all_tasks(self):
        page = render_page()
        self.assertEqual(page.count("<li "), len(TASKS))
        for task in TASKS:
            self.assertIn(task["title"], page)


if __name__ == "__main__":
    unittest.main()
