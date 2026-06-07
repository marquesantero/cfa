"""CFA Audit — trail, context, and hashing."""
from cfa._lazy import LazyLoader

__getattr__ = LazyLoader({
    "AuditTrail": ("cfa.audit.trail", "AuditTrail"),
    "AuditEvent": ("cfa.audit.trail", "AuditEvent"),
    "AuditStorageBackend": ("cfa.audit.trail", "AuditStorageBackend"),
    "InMemoryAuditStorage": ("cfa.audit.trail", "InMemoryAuditStorage"),
    "JsonLinesAuditStorage": ("cfa.audit.trail", "JsonLinesAuditStorage"),
    "ContextRegistry": ("cfa.audit.context", "ContextRegistry"),
    "InMemoryContextStorage": ("cfa.audit.context", "InMemoryContextStorage"),
    "JsonFileContextStorage": ("cfa.audit.context", "JsonFileContextStorage"),
    "hash_governance_artifact": ("cfa.audit.hashing", "hash_governance_artifact"),
    "hash_file_content": ("cfa.audit.hashing", "hash_file_content"),
})
