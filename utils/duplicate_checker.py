"""
Duplicate content detection using text similarity
"""
import hashlib
import difflib
from pathlib import Path
import json

class DuplicateChecker:
    def __init__(self, history_file="cache/content_history.json"):
        self.history_file = Path(history_file)
        self.history_file.parent.mkdir(exist_ok=True)
        self.history = self._load_history()
    
    def _load_history(self):
        """Load content history from file"""
        if not self.history_file.exists():
            return []
        
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading content history: {e}")
            return []
    
    def _save_history(self):
        """Save content history to file"""
        try:
            # Keep only last 1000 entries to prevent file from growing too large
            if len(self.history) > 1000:
                self.history = self.history[-1000:]
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving content history: {e}")
    
    def _get_content_hash(self, content):
        """Generate hash of content for quick comparison"""
        # Normalize content: lowercase, remove extra whitespace
        normalized = ' '.join(content.lower().split())
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    def _calculate_similarity(self, text1, text2):
        """
        Calculate similarity ratio between two texts
        
        Returns:
            Float between 0 and 1 (1 = identical)
        """
        # Normalize texts
        text1 = ' '.join(text1.lower().split())
        text2 = ' '.join(text2.lower().split())
        
        # Use difflib for similarity comparison
        return difflib.SequenceMatcher(None, text1, text2).ratio()
    
    def is_duplicate(self, content, threshold=0.85):
        """
        Check if content is too similar to previously generated content
        
        Args:
            content: Content to check
            threshold: Similarity threshold (0-1). Default 0.85 means 85% similar
            
        Returns:
            True if duplicate found, False otherwise
        """
        content_hash = self._get_content_hash(content)
        
        # Quick hash check first
        for entry in self.history:
            if entry['hash'] == content_hash:
                print(f"❌ Exact duplicate detected (hash match)")
                return True
        
        # Check similarity with recent entries
        recent_entries = self.history[-100:]  # Check last 100 entries
        
        for entry in recent_entries:
            similarity = self._calculate_similarity(content, entry['content_sample'])
            if similarity >= threshold:
                print(f"❌ Similar content detected (similarity: {similarity:.2%})")
                return True
        
        return False
    
    def add_content(self, content, metadata=None):
        """
        Add content to history
        
        Args:
            content: Content that was generated
            metadata: Optional metadata (app_name, platform, etc.)
        """
        content_hash = self._get_content_hash(content)
        
        # Store first 500 characters as sample for similarity checking
        content_sample = ' '.join(content.split()[:500])
        
        entry = {
            'hash': content_hash,
            'content_sample': content_sample,
            'metadata': metadata or {},
            'timestamp': str(Path().absolute())  # Simple timestamp
        }
        
        self.history.append(entry)
        self._save_history()
    
    def check_and_add(self, content, threshold=0.85, metadata=None):
        """
        Check for duplicates and add if unique
        
        Returns:
            True if content is unique (not duplicate), False if duplicate
        """
        if self.is_duplicate(content, threshold):
            return False
        
        self.add_content(content, metadata)
        return True
    
    def get_stats(self):
        """Get statistics about stored content"""
        return {
            'total_entries': len(self.history),
            'file_size': self.history_file.stat().st_size if self.history_file.exists() else 0
        }
