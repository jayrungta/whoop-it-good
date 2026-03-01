from datetime import datetime
from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, Boolean, Text,
    DateTime, Date
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class WhoopCycle(Base):
    __tablename__ = "whoop_cycles"

    id = Column(BigInteger, primary_key=True)   # integer per API spec
    user_id = Column(BigInteger, nullable=False)
    start = Column(DateTime(timezone=True))
    end = Column(DateTime(timezone=True))
    strain_score = Column(Float)
    kilojoules = Column(Float)
    avg_heart_rate = Column(Integer)
    max_heart_rate = Column(Integer)
    score_state = Column(String(50))
    synced_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class WhoopRecovery(Base):
    __tablename__ = "whoop_recovery"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cycle_id = Column(BigInteger, unique=True, nullable=False)
    sleep_id = Column(String(36))               # UUID string per API spec
    user_id = Column(BigInteger, nullable=False)
    user_calibrating = Column(Boolean)
    recovery_score = Column(Integer)
    hrv_rmssd_milli = Column(Float)
    resting_heart_rate = Column(Integer)
    spo2_percentage = Column(Float)
    skin_temp_celsius = Column(Float)
    score_state = Column(String(50))
    created_at = Column(DateTime(timezone=True))
    synced_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class WhoopSleep(Base):
    __tablename__ = "whoop_sleep"

    id = Column(String(36), primary_key=True)   # UUID string per API spec
    cycle_id = Column(BigInteger)
    user_id = Column(BigInteger, nullable=False)
    nap = Column(Boolean)
    start = Column(DateTime(timezone=True))
    end = Column(DateTime(timezone=True))
    total_in_bed_milli = Column(BigInteger)
    light_sleep_milli = Column(BigInteger)
    slow_wave_milli = Column(BigInteger)
    rem_sleep_milli = Column(BigInteger)
    awake_count = Column(Integer)               # disturbance_count
    sleep_cycle_count = Column(Integer)
    sleep_performance_pct = Column(Float)
    sleep_consistency_pct = Column(Float)
    sleep_efficiency_pct = Column(Float)
    respiratory_rate = Column(Float)
    sleep_debt_milli = Column(BigInteger)       # from score.sleep_needed.need_from_sleep_debt_milli
    score_state = Column(String(50))
    synced_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class WhoopWorkout(Base):
    __tablename__ = "whoop_workouts"

    id = Column(String(36), primary_key=True)   # UUID string per API spec
    cycle_id = Column(BigInteger)
    user_id = Column(BigInteger, nullable=False)
    sport_name = Column(String(100))
    start = Column(DateTime(timezone=True))
    end = Column(DateTime(timezone=True))
    strain_score = Column(Float)
    avg_heart_rate = Column(Integer)
    max_heart_rate = Column(Integer)
    kilojoules = Column(Float)
    distance_meter = Column(Float)
    zone_zero_milli = Column(BigInteger)
    zone_one_milli = Column(BigInteger)
    zone_two_milli = Column(BigInteger)
    zone_three_milli = Column(BigInteger)
    zone_four_milli = Column(BigInteger)
    zone_five_milli = Column(BigInteger)
    score_state = Column(String(50))
    synced_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, unique=True, nullable=False)
    alcohol_units = Column(Integer)
    stress_level = Column(Integer)              # 1–5
    caffeine = Column(Boolean)
    late_caffeine = Column(Boolean)             # after 2pm
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class AIInsight(Base):
    __tablename__ = "ai_insights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    insight_type = Column(String(50), nullable=False)  # daily / weekly / alert / qa
    content = Column(Text, nullable=False)
    data_window_start = Column(DateTime(timezone=True))
    data_window_end = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(50), nullable=False, unique=True)   # "whoop"
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    scope = Column(Text, nullable=True)
    token_type = Column(String(50), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


