import queue
import json
from typing import Dict, Any

class SeatEventBroker:
	"""In-memory broadcaster for seat status events per trip.
	This is suitable for single-process deployments. For multi-process, replace with Redis pub/sub.
	"""

	def __init__(self):
		self._trip_to_queues: Dict[int, set[queue.Queue]] = {}

	def subscribe(self, trip_id: int) -> queue.Queue:
		q: queue.Queue = queue.Queue()
		self._trip_to_queues.setdefault(trip_id, set()).add(q)
		return q

	def unsubscribe(self, trip_id: int, q: queue.Queue) -> None:
		qs = self._trip_to_queues.get(trip_id)
		if not qs:
			return
		qs.discard(q)
		if not qs:
			self._trip_to_queues.pop(trip_id, None)

	def publish(self, trip_id: int, event: Dict[str, Any]) -> None:
		for q in list(self._trip_to_queues.get(trip_id, set())):
			try:
				q.put_nowait(json.dumps(event))
			except Exception:
				pass


broker = SeatEventBroker()

