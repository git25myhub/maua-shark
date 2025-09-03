from datetime import datetime
from maua.extensions import db


class Setting(db.Model):
	__tablename__ = 'settings'

	key = db.Column(db.String(100), primary_key=True)
	value = db.Column(db.String(255), nullable=False)
	updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

	@classmethod
	def get(cls, key: str, default: str | None = None) -> str | None:
		item = cls.query.filter_by(key=key).first()
		return item.value if item else default

	@classmethod
	def set(cls, key: str, value: str) -> None:
		item = cls.query.filter_by(key=key).first()
		if item:
			item.value = value
		else:
			item = cls(key=key, value=value)
			db.session.add(item)
		db.session.commit()

	@classmethod
	def get_int(cls, key: str, default: int) -> int:
		val = cls.get(key)
		try:
			return int(val) if val is not None else default
		except ValueError:
			return default


