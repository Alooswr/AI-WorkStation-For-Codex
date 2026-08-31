from __future__ import annotations

import unittest

from firmware_mcp_server.log_normalizer import classify_log_line, normalize_command_logs


class LogNormalizerTests(unittest.TestCase):
    def test_classifies_keil_summary_without_false_error(self) -> None:
        self.assertEqual(classify_log_line("Program Size: Code=123 RO-data=4 RW-data=5 ZI-data=6"), "Info")
        self.assertEqual(classify_log_line("0 Error(s), 1 Warning(s)."), "Warning")
        self.assertEqual(classify_log_line("1 Error(s), 0 Warning(s)."), "Error")

    def test_normalizes_command_output_to_three_levels(self) -> None:
        logs = normalize_command_logs(
            "compile ok\n0 Error(s), 1 Warning(s).",
            "fatal error: missing header",
        )

        self.assertEqual(logs["levels"], ["Error", "Warning", "Info"])
        self.assertEqual(logs["counts"]["Error"], 1)
        self.assertEqual(logs["counts"]["Warning"], 1)
        self.assertEqual(logs["counts"]["Info"], 1)


if __name__ == "__main__":
    unittest.main()
