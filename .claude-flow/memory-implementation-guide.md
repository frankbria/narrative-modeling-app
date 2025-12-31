# Memory Implementation Guide for Swarm Agents

## Overview

This guide provides concrete implementation patterns for integrating the collective memory system into the narrative-modeling-app. It covers the Python backend, TypeScript frontend, and MCP server integration patterns.

---

## Part 1: Memory Store Implementation

### 1.1 Core MemoryStore Class

```python
# shared/memory/store.py
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
import json
import sqlite3
from dataclasses import dataclass, asdict
import hashlib

@dataclass
class MemoryEntry:
    """Single memory entry"""
    key: str                              # "backend/api/specs/dataset-upload"
    namespace: str                        # "backend/api/specs"
    artifact_type: str                    # "spec", "pattern", "note", etc.
    content: str                          # The actual content
    tags: List[str]                       # Searchable tags
    metadata: Dict[str, Any]              # Custom metadata
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]        # TTL expiration
    created_by: str                       # Agent that created it
    version: int = 1
    parent_version: Optional[int] = None  # For versioning

@dataclass
class SearchResult:
    """Search result"""
    entries: List[MemoryEntry]
    total_count: int
    query_time_ms: float

class MemoryStore:
    """Unified memory store for swarm agents"""

    def __init__(
        self,
        db_path: str = ".swarm/memory.db",
        persistent_dir: str = ".claude-flow/memory"
    ):
        self.db_path = Path(db_path)
        self.persistent_dir = Path(persistent_dir)
        self.conn = None
        self._init_database()
        self._init_filesystem()

    def _init_database(self):
        """Initialize SQLite database for ephemeral memory"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id TEXT PRIMARY KEY,
                namespace TEXT NOT NULL,
                key TEXT NOT NULL UNIQUE,
                artifact_type TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT,
                metadata TEXT,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                expires_at TIMESTAMP,
                created_by TEXT,
                version INTEGER DEFAULT 1,
                parent_version INTEGER
            )
        """)

        # Indexes for fast searching
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_namespace ON memory(namespace)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tags ON memory(tags)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_expires_at ON memory(expires_at)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_artifact_type ON memory(artifact_type)"
        )

        self.conn.commit()

    def _init_filesystem(self):
        """Initialize filesystem for persistent memory"""
        self.persistent_dir.mkdir(parents=True, exist_ok=True)

    def set(
        self,
        key: str,
        content: str,
        tags: List[str],
        artifact_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None,
        created_by: str = "system",
    ) -> MemoryEntry:
        """
        Store a memory entry.

        Args:
            key: Path-like key (e.g., "backend/api/specs/dataset-upload")
            content: The actual content
            tags: Searchable tags
            artifact_type: Type of artifact (inferred from key if None)
            metadata: Additional metadata
            ttl: Time-to-live in seconds (None = no expiration)
            created_by: Agent that created this entry

        Returns:
            MemoryEntry that was stored
        """
        # Determine artifact type from path
        if artifact_type is None:
            artifact_type = self._infer_artifact_type(key)

        # Determine storage location
        is_persistent = artifact_type in ["spec", "pattern", "test", "decision", "security"]

        now = datetime.utcnow()
        expires_at = None if is_persistent else (now + timedelta(seconds=ttl or 604800))

        entry = MemoryEntry(
            key=key,
            namespace=self._extract_namespace(key),
            artifact_type=artifact_type,
            content=content,
            tags=tags,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            created_by=created_by,
            version=1
        )

        # Store in appropriate location
        if is_persistent:
            self._save_persistent(entry)
        else:
            self._save_ephemeral(entry)

        return entry

    def get(self, key: str) -> Optional[MemoryEntry]:
        """Retrieve a memory entry by key"""
        # Try ephemeral first
        entry = self._load_ephemeral(key)
        if entry:
            return entry

        # Try persistent
        entry = self._load_persistent(key)
        if entry and entry.expires_at and entry.expires_at < datetime.utcnow():
            # Entry expired
            return None

        return entry

    def search(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        namespace: Optional[str] = None,
        artifact_type: Optional[str] = None,
        app: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> SearchResult:
        """
        Search memory entries.

        Args:
            query: Full-text search query
            tags: Search by tags (match any)
            namespace: Filter by namespace
            artifact_type: Filter by artifact type
            app: Filter by app (frontend, backend, mcp)
            limit: Max results
            offset: Pagination offset

        Returns:
            SearchResult with matching entries
        """
        import time
        start = time.time()

        # Build SQL query
        conditions = []
        params = []

        if namespace:
            conditions.append("namespace LIKE ?")
            params.append(f"{namespace}%")

        if artifact_type:
            conditions.append("artifact_type = ?")
            params.append(artifact_type)

        if app:
            conditions.append("namespace LIKE ?")
            params.append(f"{app}%")

        if tags:
            # Match any tag
            tag_conditions = []
            for tag in tags:
                tag_conditions.append("tags LIKE ?")
                params.append(f"%{tag}%")
            if tag_conditions:
                conditions.append(f"({' OR '.join(tag_conditions)})")

        if query:
            conditions.append("(content LIKE ? OR key LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])

        # Clean up expired entries while searching
        self.conn.execute(
            "DELETE FROM memory WHERE expires_at IS NOT NULL AND expires_at < ?"
        )
        self.conn.commit()

        # Build final query
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT * FROM memory
            WHERE {where_clause}
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        cursor = self.conn.execute(sql, params)
        rows = cursor.fetchall()

        entries = [self._row_to_entry(row) for row in rows]

        elapsed = (time.time() - start) * 1000

        return SearchResult(
            entries=entries,
            total_count=len(entries),
            query_time_ms=elapsed
        )

    def list_namespace(
        self,
        namespace: str,
        recursive: bool = True,
        limit: int = 100
    ) -> List[MemoryEntry]:
        """
        List all entries in a namespace.

        Args:
            namespace: Namespace to list (e.g., "frontend/components")
            recursive: Include sub-namespaces
            limit: Max results

        Returns:
            List of entries in namespace
        """
        pattern = f"{namespace}%" if recursive else f"{namespace}/*"
        return self.search(namespace=namespace, limit=limit).entries

    def load_context(
        self,
        app: str,
        domain: str,
        feature: str
    ) -> Dict[str, List[MemoryEntry]]:
        """
        Load all context for a feature (specs, patterns, tests, decisions).

        Args:
            app: App name (frontend, backend, mcp)
            domain: Domain (api, components, services, etc.)
            feature: Feature name

        Returns:
            Dictionary with specs, patterns, tests, decisions
        """
        namespace = f"{app}/{domain}"

        context = {
            "specs": self.search(
                namespace=f"{namespace}/specs/{feature}",
                artifact_type="spec"
            ).entries,
            "patterns": self.search(
                namespace=f"{namespace}/patterns",
                artifact_type="pattern",
                limit=20
            ).entries,
            "tests": self.search(
                namespace=f"{namespace}/tests",
                artifact_type="test",
                limit=20
            ).entries,
            "decisions": self.search(
                tags=["decision"],
                app=app,
                limit=10
            ).entries,
        }

        return context

    def _save_ephemeral(self, entry: MemoryEntry):
        """Save to SQLite database (ephemeral)"""
        entry_id = hashlib.md5(entry.key.encode()).hexdigest()

        self.conn.execute("""
            INSERT OR REPLACE INTO memory
            (id, namespace, key, artifact_type, content, tags, metadata,
             created_at, updated_at, expires_at, created_by, version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry_id,
            entry.namespace,
            entry.key,
            entry.artifact_type,
            entry.content,
            ",".join(entry.tags),
            json.dumps(entry.metadata),
            entry.created_at,
            entry.updated_at,
            entry.expires_at,
            entry.created_by,
            entry.version
        ))
        self.conn.commit()

    def _save_persistent(self, entry: MemoryEntry):
        """Save to filesystem (persistent)"""
        # Create directory structure
        file_path = self.persistent_dir / entry.key.replace("/", "/") / "content.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Save content
        with open(file_path, "w") as f:
            f.write(entry.content)

        # Save metadata
        metadata_path = file_path.parent / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump({
                "tags": entry.tags,
                "artifact_type": entry.artifact_type,
                "created_at": entry.created_at.isoformat(),
                "updated_at": entry.updated_at.isoformat(),
                "created_by": entry.created_by,
                "metadata": entry.metadata
            }, f, indent=2)

        # Also save to database for searching
        self._save_ephemeral(entry)

    def _load_ephemeral(self, key: str) -> Optional[MemoryEntry]:
        """Load from SQLite database"""
        cursor = self.conn.execute(
            "SELECT * FROM memory WHERE key = ?",
            (key,)
        )
        row = cursor.fetchone()
        return self._row_to_entry(row) if row else None

    def _load_persistent(self, key: str) -> Optional[MemoryEntry]:
        """Load from filesystem"""
        file_path = self.persistent_dir / key / "content.md"
        if not file_path.exists():
            return None

        with open(file_path, "r") as f:
            content = f.read()

        metadata_path = file_path.parent / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            return MemoryEntry(
                key=key,
                namespace=self._extract_namespace(key),
                artifact_type=metadata.get("artifact_type"),
                content=content,
                tags=metadata.get("tags", []),
                metadata=metadata.get("metadata", {}),
                created_at=datetime.fromisoformat(metadata.get("created_at")),
                updated_at=datetime.fromisoformat(metadata.get("updated_at")),
                expires_at=None,
                created_by=metadata.get("created_by", "unknown")
            )

        return None

    def _extract_namespace(self, key: str) -> str:
        """Extract namespace from key"""
        # "backend/api/specs/dataset-upload" -> "backend/api/specs"
        parts = key.split("/")
        return "/".join(parts[:-1])

    def _infer_artifact_type(self, key: str) -> str:
        """Infer artifact type from key path"""
        if "/specs/" in key:
            return "spec"
        elif "/patterns/" in key:
            return "pattern"
        elif "/tests/" in key:
            return "test"
        elif "/decisions/" in key or "adr-" in key:
            return "decision"
        elif "/notes/" in key:
            return "note"
        elif "/security/" in key:
            return "security"
        else:
            return "document"

    def _row_to_entry(self, row) -> Optional[MemoryEntry]:
        """Convert database row to MemoryEntry"""
        if not row:
            return None

        return MemoryEntry(
            key=row[3],
            namespace=row[2],
            artifact_type=row[4],
            content=row[5],
            tags=row[6].split(",") if row[6] else [],
            metadata=json.loads(row[7]) if row[7] else {},
            created_at=datetime.fromisoformat(row[8]),
            updated_at=datetime.fromisoformat(row[9]),
            expires_at=datetime.fromisoformat(row[10]) if row[10] else None,
            created_by=row[11] or "system",
            version=row[12] or 1,
            parent_version=row[13]
        )

    def cleanup_expired(self):
        """Remove expired entries"""
        self.conn.execute(
            "DELETE FROM memory WHERE expires_at IS NOT NULL AND expires_at < ?"
        )
        self.conn.commit()

    def optimize(self):
        """Optimize database"""
        self.conn.execute("VACUUM")
        self.conn.execute("ANALYZE")
        self.conn.commit()

    def stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        cursor = self.conn.execute("SELECT COUNT(*) FROM memory")
        total_entries = cursor.fetchone()[0]

        cursor = self.conn.execute(
            "SELECT artifact_type, COUNT(*) FROM memory GROUP BY artifact_type"
        )
        by_type = dict(cursor.fetchall())

        cursor = self.conn.execute(
            "SELECT app_name, COUNT(*) FROM "
            "(SELECT SUBSTR(namespace, 1, INSTR(namespace, '/') - 1) as app_name "
            "FROM memory) GROUP BY app_name"
        )
        by_app = dict(cursor.fetchall())

        return {
            "total_entries": total_entries,
            "by_type": by_type,
            "by_app": by_app,
            "db_size_mb": self.db_path.stat().st_size / (1024 * 1024),
        }
```

---

## Part 2: Agent Integration

### 2.1 Agent Base Class with Memory Support

```python
# shared/agents/agent_base.py
from typing import Optional, Dict, Any
from shared.memory.store import MemoryStore, MemoryEntry

class SwarmAgent:
    """Base class for swarm agents with memory support"""

    def __init__(
        self,
        agent_id: str,
        role: str,
        app: str,
        domain: str,
        memory_store: Optional[MemoryStore] = None
    ):
        self.agent_id = agent_id
        self.role = role
        self.app = app
        self.domain = domain
        self.memory = memory_store or MemoryStore()
        self.context = {}
        self.task = None

    def on_task_start(self, task_id: str, feature: str, context_config: Optional[Dict] = None):
        """Initialize task with memory context"""
        self.task = {
            "id": task_id,
            "feature": feature,
            "started_at": datetime.utcnow()
        }

        # Load context from memory
        config = context_config or {
            "include": ["specs", "patterns", "tests", "decisions"]
        }

        self.context = self.memory.load_context(
            app=self.app,
            domain=self.domain,
            feature=feature
        )

        # Create system prompt with context
        self._prepare_system_prompt()

    def _prepare_system_prompt(self) -> str:
        """Generate system prompt with memory context"""
        prompt_parts = []

        if self.context.get("specs"):
            prompt_parts.append(
                f"\n## Specifications ({len(self.context['specs'])} items)\n"
            )
            for spec in self.context["specs"][:5]:  # Top 5
                prompt_parts.append(f"- {spec.key}: {spec.tags}")

        if self.context.get("patterns"):
            prompt_parts.append(
                f"\n## Available Patterns ({len(self.context['patterns'])} items)\n"
            )
            for pattern in self.context["patterns"][:5]:  # Top 5
                prompt_parts.append(f"- {pattern.key}")

        if self.context.get("decisions"):
            prompt_parts.append(
                f"\n## Relevant Decisions ({len(self.context['decisions'])} items)\n"
            )
            for decision in self.context["decisions"][:3]:  # Top 3
                prompt_parts.append(f"- {decision.key}: {decision.tags}")

        return "".join(prompt_parts)

    def store_implementation_note(
        self,
        feature: str,
        content: str,
        tags: Optional[List[str]] = None
    ):
        """Store session progress note"""
        key = f"{self.app}/{self.domain}/notes/{feature}-implementation"

        default_tags = ["note", "implementation", feature]
        if tags:
            default_tags.extend(tags)

        self.memory.set(
            key=key,
            content=content,
            tags=default_tags,
            artifact_type="note",
            created_by=self.agent_id,
            ttl=604800  # 7 days
        )

    def store_decision(
        self,
        decision_id: str,
        adr_content: str,
        tags: Optional[List[str]] = None
    ):
        """Store architectural decision"""
        key = f"shared/decisions/{decision_id}"

        default_tags = ["decision", "accepted"]
        if tags:
            default_tags.extend(tags)

        self.memory.set(
            key=key,
            content=adr_content,
            tags=default_tags,
            artifact_type="decision",
            created_by=self.agent_id
        )

    def retrieve_pattern(self, pattern_name: str) -> Optional[MemoryEntry]:
        """Retrieve a specific pattern"""
        key = f"{self.app}/{self.domain}/patterns/{pattern_name}"
        return self.memory.get(key)

    def find_similar_patterns(self, query: str, limit: int = 5) -> List[MemoryEntry]:
        """Find similar patterns in domain"""
        results = self.memory.search(
            query=query,
            tags=["pattern"],
            app=self.app,
            limit=limit
        )
        return results.entries

    def find_security_patterns(self) -> List[MemoryEntry]:
        """Find security patterns for current domain"""
        results = self.memory.search(
            tags=["security"],
            app=self.app,
            limit=10
        )
        return results.entries
```

### 2.2 Agent Registry

```python
# shared/agents/registry.py
from typing import Dict, Optional
from shared.agents.agent_base import SwarmAgent

class AgentRegistry:
    """Registry of available agents in the swarm"""

    agents: Dict[str, type] = {}

    @classmethod
    def register(cls, agent_id: str):
        """Decorator to register agent"""
        def decorator(agent_class):
            cls.agents[agent_id] = agent_class
            return agent_class
        return decorator

    @classmethod
    def get_agent(
        cls,
        agent_id: str,
        app: str,
        domain: str,
        memory_store: Optional[MemoryStore] = None
    ) -> Optional[SwarmAgent]:
        """Get agent instance"""
        if agent_id not in cls.agents:
            return None

        agent_class = cls.agents[agent_id]
        return agent_class(
            agent_id=agent_id,
            app=app,
            domain=domain,
            memory_store=memory_store
        )

# Example agent registrations
@AgentRegistry.register("typescript-expert")
class TypeScriptExpert(SwarmAgent):
    def __init__(self, **kwargs):
        super().__init__(role="TypeScript Expert", **kwargs)

@AgentRegistry.register("python-expert")
class PythonExpert(SwarmAgent):
    def __init__(self, **kwargs):
        super().__init__(role="Python Expert", **kwargs)

@AgentRegistry.register("architecture-reviewer")
class ArchitectureReviewer(SwarmAgent):
    def __init__(self, **kwargs):
        super().__init__(role="Architecture Reviewer", **kwargs)
```

---

## Part 3: Common Patterns

### 3.1 Feature Implementation Workflow

```python
# Example: Backend service implementing recipe export

class RecipeExportWorkflow:
    def __init__(self, agent: SwarmAgent):
        self.agent = agent
        self.memory = agent.memory
        self.feature = "recipe-bulk-export"

    async def execute(self):
        """Execute feature implementation"""

        # 1. Load specification
        spec = self.memory.get(
            f"backend/api/specs/{self.feature}"
        )

        print(f"Specification:\n{spec.content}")

        # 2. Find similar patterns
        patterns = self.agent.find_similar_patterns("async export")
        print(f"\nFound {len(patterns)} similar patterns")

        # 3. Load test fixtures
        test_fixtures = self.memory.get(
            f"backend/api/tests/unit/{self.feature}/test-fixtures"
        )

        # 4. Implement service
        implementation = await self._implement_service(spec, patterns)

        # 5. Store implementation note
        self.agent.store_implementation_note(
            feature=self.feature,
            content=f"""
            # Session Implementation Log

            ## Day 1: API and Service Layer
            - Implemented async job queue pattern
            - Created DatasetExportService with background task
            - Added job tracking and progress endpoints

            ## Architecture Decision
            Using Redis-backed Celery for:
            - Async processing (user not blocked)
            - Job persistence (can restart tasks)
            - Progress tracking (client polling)

            ## Performance
            - Export 1MB CSV: 200ms
            - Export 100MB CSV: 15s (acceptable)
            - Memory usage: Streaming chunks to prevent OOM
            """,
            tags=["async", "export", "background-jobs"]
        )

        return implementation
```

### 3.2 Security Review Pattern

```python
class SecurityReviewWorkflow:
    def __init__(self, agent: SwarmAgent):
        self.agent = agent
        self.memory = agent.memory

    async def review_code(self, code_path: str):
        """Security review with memory context"""

        # 1. Load security patterns for this app
        security_patterns = self.agent.find_security_patterns()

        print("Security Patterns to check:")
        for pattern in security_patterns:
            print(f"  - {pattern.key}: {pattern.tags}")

        # 2. Check code against patterns
        issues = []

        # 3. Store findings
        if issues:
            self.memory.set(
                f"{self.agent.app}/security/audit-{datetime.now().date()}",
                content=f"""
                # Security Audit

                ## Issues Found
                {issues}

                ## Patterns Applied
                {[p.key for p in security_patterns]}

                ## Recommendations
                - See: shared/security/sql-injection-prevention
                - See: backend/security/input-validation-rules
                """,
                tags=["security", "audit"],
                artifact_type="security",
                created_by=self.agent.agent_id
            )
```

---

## Part 4: CLI Tools

### 4.1 Memory Management CLI

```bash
# memory-cli.py - CLI for memory management

import typer
from rich.console import Console
from shared.memory.store import MemoryStore

app = typer.Typer()
console = Console()
memory = MemoryStore()

@app.command()
def search(
    query: str = typer.Argument(...),
    tags: str = typer.Option(None),
    app_name: str = typer.Option(None),
    limit: int = typer.Option(10)
):
    """Search memory"""
    tag_list = tags.split(",") if tags else None

    results = memory.search(
        query=query,
        tags=tag_list,
        app=app_name,
        limit=limit
    )

    console.print(f"Found {results.total_count} results in {results.query_time_ms:.1f}ms\n")

    for entry in results.entries:
        console.print(f"[bold]{entry.key}[/bold]")
        console.print(f"  Type: {entry.artifact_type}")
        console.print(f"  Tags: {', '.join(entry.tags)}")
        console.print(f"  Updated: {entry.updated_at}")
        console.print()

@app.command()
def get(key: str):
    """Get specific entry"""
    entry = memory.get(key)
    if entry:
        console.print(entry.content)
    else:
        console.print(f"[red]Entry not found: {key}[/red]")

@app.command()
def list(namespace: str, recursive: bool = True):
    """List entries in namespace"""
    entries = memory.list_namespace(namespace, recursive=recursive)
    console.print(f"Entries in {namespace}:")
    for entry in entries:
        console.print(f"  - {entry.key}")

@app.command()
def stats():
    """Show memory statistics"""
    stats = memory.stats()
    console.print_json(data=stats)

@app.command()
def cleanup():
    """Clean up expired entries"""
    memory.cleanup_expired()
    console.print("[green]Cleanup complete[/green]")

if __name__ == "__main__":
    app()
```

---

## Part 5: Testing

### 5.1 Memory Store Tests

```python
# tests/test_memory/test_store.py
import pytest
from shared.memory.store import MemoryStore, MemoryEntry
from datetime import datetime, timedelta

@pytest.fixture
def memory():
    """Fresh memory store for testing"""
    return MemoryStore(db_path=":memory:")  # Use in-memory SQLite

def test_set_and_get_persistent(memory):
    """Test storing and retrieving persistent entry"""
    memory.set(
        key="backend/api/specs/dataset-upload",
        content="Dataset Upload Specification",
        tags=["spec", "api", "dataset"],
        created_by="test-agent"
    )

    entry = memory.get("backend/api/specs/dataset-upload")
    assert entry is not None
    assert entry.content == "Dataset Upload Specification"
    assert "spec" in entry.tags

def test_set_and_get_ephemeral(memory):
    """Test storing and retrieving ephemeral entry"""
    memory.set(
        key="frontend/components/notes/feature-progress",
        content="Day 1: Started implementation",
        tags=["note", "implementation"],
        ttl=604800,  # 7 days
        created_by="test-agent"
    )

    entry = memory.get("frontend/components/notes/feature-progress")
    assert entry is not None
    assert entry.expires_at is not None

def test_search_by_tags(memory):
    """Test searching by tags"""
    memory.set(
        "backend/api/patterns/async-task-queue",
        "async pattern code",
        tags=["pattern", "async", "queue"]
    )

    results = memory.search(tags=["pattern", "async"])
    assert len(results.entries) > 0
    assert any("pattern" in e.tags for e in results.entries)

def test_search_by_query(memory):
    """Test full-text search"""
    memory.set(
        "backend/api/specs/auth",
        "JWT authentication specification",
        tags=["spec", "auth"]
    )

    results = memory.search(query="JWT authentication")
    assert len(results.entries) > 0

def test_namespace_discovery(memory):
    """Test namespace listing"""
    memory.set("backend/api/specs/dataset", "spec", tags=["spec"])
    memory.set("backend/api/patterns/async", "pattern", tags=["pattern"])
    memory.set("backend/services/patterns/transaction", "pattern", tags=["pattern"])

    entries = memory.list_namespace("backend/api", recursive=True)
    assert len(entries) >= 2

def test_load_context(memory):
    """Test context loading for feature"""
    # Setup test data
    memory.set("backend/api/specs/export", "spec content", tags=["spec"])
    memory.set("backend/api/patterns/async-export", "pattern code", tags=["pattern"])
    memory.set("backend/api/tests/export", "test fixture", tags=["test"])

    context = memory.load_context("backend", "api", "export")

    assert "specs" in context
    assert "patterns" in context
    assert "tests" in context
```

---

## Implementation Checklist

- [ ] Create `shared/memory/store.py` with MemoryStore class
- [ ] Create `shared/agents/agent_base.py` with SwarmAgent class
- [ ] Create `shared/agents/registry.py` with agent registration
- [ ] Create CLI tool `scripts/memory-cli.py`
- [ ] Add memory initialization to app startup
- [ ] Create tests in `tests/test_memory/`
- [ ] Document integration points in README
- [ ] Create example agent workflows
- [ ] Add memory monitoring/stats endpoint
- [ ] Set up background cleanup task for expired entries

---

## Next Steps

1. **Frontend Integration**: Create TypeScript version of MemoryStore
2. **MCP Integration**: Add memory access to MCP tools
3. **Monitoring Dashboard**: Create visualization of memory usage
4. **Team Convention**: Document team guidelines for memory entries
