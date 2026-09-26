from __future__ import annotations

import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.agent_hosted_repository_worker import HostedRunInterrupted, hard_run_deadline  # noqa: E402


class HostedHardDeadlineTest(unittest.TestCase):
    def test_timer_is_armed_and_restored(self):
        with patch("tools.agent_hosted_repository_worker.signal.getitimer", return_value=(0.0, 0.0)), \
             patch("tools.agent_hosted_repository_worker.signal.getsignal", return_value="previous") as getsignal, \
             patch("tools.agent_hosted_repository_worker.signal.signal") as signal_call, \
             patch("tools.agent_hosted_repository_worker.signal.setitimer") as setitimer:
            with hard_run_deadline(12.5):
                pass
        getsignal.assert_called_once()
        self.assertEqual(setitimer.call_args_list[0].args[1], 12.5)
        self.assertEqual(setitimer.call_args_list[-1].args[1], 0.0)
        self.assertEqual(signal_call.call_args_list[-1].args[1], "previous")

    def test_alarm_handler_raises_non_retry_interrupt(self):
        captured = {}

        def install(_sig, handler):
            if callable(handler):
                captured["handler"] = handler

        with patch("tools.agent_hosted_repository_worker.signal.getitimer", return_value=(0.0, 0.0)), \
             patch("tools.agent_hosted_repository_worker.signal.getsignal", return_value="previous"), \
             patch("tools.agent_hosted_repository_worker.signal.signal", side_effect=install), \
             patch("tools.agent_hosted_repository_worker.signal.setitimer"):
            with self.assertRaisesRegex(HostedRunInterrupted, "hosted_hard_deadline_exceeded"):
                with hard_run_deadline(5):
                    captured["handler"](None, None)

    def test_existing_process_timer_is_not_overwritten(self):
        with patch("tools.agent_hosted_repository_worker.signal.getitimer", return_value=(4.0, 0.0)), \
             patch("tools.agent_hosted_repository_worker.signal.setitimer") as setitimer:
            with self.assertRaisesRegex(HostedRunInterrupted, "hosted_hard_deadline_timer_already_in_use"):
                with hard_run_deadline(5):
                    pass
        setitimer.assert_not_called()

    def test_background_thread_context_fails_before_timer_use(self):
        with patch("tools.agent_hosted_repository_worker.threading.current_thread", return_value=object()), \
             patch("tools.agent_hosted_repository_worker.threading.main_thread", return_value=object()), \
             patch("tools.agent_hosted_repository_worker.signal.setitimer") as setitimer:
            with self.assertRaisesRegex(HostedRunInterrupted, "hosted_hard_deadline_unavailable_off_main_thread"):
                with hard_run_deadline(5):
                    pass
        setitimer.assert_not_called()

    def test_invalid_deadline_fails_before_timer_use(self):
        for value in (0, -1, True, None):
            with self.subTest(value=value):
                with self.assertRaises((ValueError, TypeError)):
                    with hard_run_deadline(value):
                        pass


if __name__ == "__main__":
    unittest.main()
