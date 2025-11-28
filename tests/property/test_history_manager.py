"""Property-based tests for HistoryManager.

**Feature: gemini-voice-writer-v2, Properties 14-17**
**Validates: Requirements 8.1, 8.2, 8.4, 8.5**
"""
import os
import tempfile
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume

from utils.history_manager import HistoryManager, TranscriptionRecord


# Strategy for generating valid transcription records
record_strategy = st.builds(
    TranscriptionRecord,
    text=st.text(min_size=1, max_size=500),
    duration=st.floats(min_value=0.1, max_value=3600.0, allow_nan=False, allow_infinity=False),
    provider=st.sampled_from(["gemini", "openrouter", "openai"]),
    model=st.text(min_size=1, max_size=50),
    cost=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
    timestamp=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)),
    audio_path=st.one_of(st.none(), st.text(min_size=1, max_size=100))
)


@given(record=record_strategy)
@settings(max_examples=100)
def test_history_storage_roundtrip(record):
    """
    **Feature: gemini-voice-writer-v2, Property 14: History Storage Round-Trip**
    
    For any TranscriptionResult, storing in SQLite and retrieving by ID 
    SHALL return a record with identical text, duration, provider, model, and cost values.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test_history.db')
        manager = HistoryManager(db_path=db_path)
        
        try:
            # Store record
            record_id = manager.add(record)
            
            # Retrieve record
            retrieved = manager.get_by_id(record_id)
            
            assert retrieved is not None, "Record should be retrievable"
            assert retrieved.text == record.text, f"Text mismatch: {record.text} != {retrieved.text}"
            assert abs(retrieved.duration - record.duration) < 0.001, "Duration mismatch"
            assert retrieved.provider == record.provider, "Provider mismatch"
            assert retrieved.model == record.model, "Model mismatch"
            assert abs(retrieved.cost - record.cost) < 0.001, "Cost mismatch"
        finally:
            manager.close()


@given(records=st.lists(record_strategy, min_size=2, max_size=10))
@settings(max_examples=50)
def test_history_ordering(records):
    """
    **Feature: gemini-voice-writer-v2, Property 15: History Ordering**
    
    For any set of transcription records, the history query 
    SHALL return them in reverse chronological order (newest first).
    """
    # Ensure unique timestamps
    for i, record in enumerate(records):
        record.timestamp = datetime(2024, 1, 1) + timedelta(hours=i)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test_history.db')
        manager = HistoryManager(db_path=db_path)
        
        try:
            # Add all records
            for record in records:
                manager.add(record)
            
            # Get all records
            retrieved = manager.get_page(page=1, per_page=100)
            
            # Verify reverse chronological order
            for i in range(len(retrieved) - 1):
                assert retrieved[i].timestamp >= retrieved[i + 1].timestamp, \
                    f"Records not in reverse chronological order: {retrieved[i].timestamp} < {retrieved[i + 1].timestamp}"
        finally:
            manager.close()


@given(record=record_strategy)
@settings(max_examples=100)
def test_history_deletion_consistency(record):
    """
    **Feature: gemini-voice-writer-v2, Property 16: History Deletion Consistency**
    
    For any existing record ID, deletion SHALL remove exactly that record,
    and subsequent queries SHALL not return it.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test_history.db')
        manager = HistoryManager(db_path=db_path)
        
        try:
            # Add record
            record_id = manager.add(record)
            
            # Verify it exists
            assert manager.get_by_id(record_id) is not None
            
            # Delete record
            deleted = manager.delete(record_id)
            assert deleted is True, "Delete should return True for existing record"
            
            # Verify it's gone
            assert manager.get_by_id(record_id) is None, "Record should not exist after deletion"
            
            # Verify delete returns False for non-existent record
            deleted_again = manager.delete(record_id)
            assert deleted_again is False, "Delete should return False for non-existent record"
        finally:
            manager.close()


@given(
    records=st.lists(record_strategy, min_size=3, max_size=10),
    search_provider=st.sampled_from(["gemini", "openrouter", "openai"])
)
@settings(max_examples=50)
def test_history_search_filtering(records, search_provider):
    """
    **Feature: gemini-voice-writer-v2, Property 17: History Search Filtering**
    
    For any search query and filter combination, all returned results 
    SHALL match the query text AND satisfy all filter conditions.
    """
    # Ensure at least one record has the search provider
    records[0].provider = search_provider
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test_history.db')
        manager = HistoryManager(db_path=db_path)
        
        try:
            # Add all records
            for record in records:
                manager.add(record)
            
            # Search with provider filter
            results = manager.search(filters={'provider': search_provider})
            
            # Verify all results match the filter
            for result in results:
                assert result.provider == search_provider, \
                    f"Result provider {result.provider} doesn't match filter {search_provider}"
        finally:
            manager.close()


@given(
    records=st.lists(record_strategy, min_size=2, max_size=5),
    search_text=st.text(min_size=3, max_size=10, alphabet=st.characters(whitelist_categories=('L',)))
)
@settings(max_examples=50)
def test_history_text_search(records, search_text):
    """Test that text search returns only matching records."""
    assume(len(search_text.strip()) > 0)
    
    # Ensure first record contains search text
    records[0].text = f"prefix {search_text} suffix"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test_history.db')
        manager = HistoryManager(db_path=db_path)
        
        try:
            for record in records:
                manager.add(record)
            
            results = manager.search(query=search_text)
            
            # All results should contain the search text
            for result in results:
                assert search_text.lower() in result.text.lower(), \
                    f"Result text '{result.text}' doesn't contain '{search_text}'"
        finally:
            manager.close()


def test_pagination():
    """Test that pagination works correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test_history.db')
        manager = HistoryManager(db_path=db_path)
        
        try:
            # Add 25 records
            for i in range(25):
                record = TranscriptionRecord(
                    text=f"Record {i}",
                    duration=1.0,
                    provider="gemini",
                    model="test",
                    timestamp=datetime(2024, 1, 1) + timedelta(hours=i)
                )
                manager.add(record)
            
            # Get first page (20 items)
            page1 = manager.get_page(page=1, per_page=20)
            assert len(page1) == 20
            
            # Get second page (5 items)
            page2 = manager.get_page(page=2, per_page=20)
            assert len(page2) == 5
            
            # Verify no overlap
            page1_ids = {r.id for r in page1}
            page2_ids = {r.id for r in page2}
            assert page1_ids.isdisjoint(page2_ids), "Pages should not overlap"
        finally:
            manager.close()


def test_total_count():
    """Test that total count is accurate."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test_history.db')
        manager = HistoryManager(db_path=db_path)
        
        try:
            assert manager.get_total_count() == 0
            
            for i in range(5):
                record = TranscriptionRecord(
                    text=f"Record {i}",
                    duration=1.0,
                    provider="gemini",
                    model="test"
                )
                manager.add(record)
            
            assert manager.get_total_count() == 5
        finally:
            manager.close()
