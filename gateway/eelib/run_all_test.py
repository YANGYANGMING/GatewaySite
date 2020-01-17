import unittest
import HtmlTestRunner

test_suite = unittest.TestSuite()
all_cases = unittest.defaultTestLoader.discover('.', 'test_*.py')

for case in all_cases:
    test_suite.addTest(case)

runner = HtmlTestRunner.HTMLTestRunner(output='report')
runner.run(test_suite)
