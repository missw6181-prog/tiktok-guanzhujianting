import logging
import threading
from typing import Optional

from sqlalchemy import select

from app.database import SessionLocal
from app.models import MonitorTask, User
from app.monitor.task_status import STATUS_IDLE
from app.monitor.worker import TaskWorker, update_task_status

logger = logging.getLogger("follow_monitor.manager")

_manager: Optional["MonitorManager"] = None


def get_monitor_manager() -> "MonitorManager":
    global _manager
    if _manager is None:
        _manager = MonitorManager()
    return _manager


class MonitorManager:
    def __init__(self) -> None:
        self._workers = {}  # task_id -> (TaskWorker, stop_event)
        self._lock = threading.Lock()
        self._sync_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, name="monitor-manager", daemon=True)
        self._thread.start()
        logger.info("MonitorManager 已启动")

    def stop(self) -> None:
        self._stop_event.set()
        self._sync_event.set()
        self._stop_all_workers()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("MonitorManager 已停止")

    def request_sync(self) -> None:
        self._sync_event.set()

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            self._sync()
            self._sync_event.wait(timeout=10)
            self._sync_event.clear()

    def _sync(self) -> None:
        with SessionLocal() as db:
            rows = db.scalars(
                select(MonitorTask.id)
                .join(User, User.id == MonitorTask.user_id)
                .where(MonitorTask.enabled.is_(True), User.status == "active")
            ).all()
            desired = set(rows)

        with self._lock:
            current = set(self._workers.keys())
            for task_id in current - desired:
                self._stop_worker(task_id)
            for task_id in desired - current:
                stop_event = threading.Event()
                worker = TaskWorker(task_id, stop_event)
                self._workers[task_id] = (worker, stop_event)
                worker.start()
                logger.info("已启动监控任务 #%s", task_id)

    def _stop_worker(self, task_id: int) -> None:
        entry = self._workers.pop(task_id, None)
        if entry is None:
            return
        worker, stop_event = entry
        stop_event.set()
        worker.join(timeout=5)
        update_task_status(task_id, STATUS_IDLE)
        logger.info("已停止监控任务 #%s", task_id)

    def _stop_all_workers(self) -> None:
        with self._lock:
            for task_id in list(self._workers.keys()):
                self._stop_worker(task_id)
