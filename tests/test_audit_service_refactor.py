from app import AuditLog, db, log_audit


def test_log_audit_commit_false_requires_manual_commit(client, test_user):
    before = AuditLog.query.count()

    log_audit("deferred_action", user_id=test_user.id, commit=False)
    db.session.flush()
    assert AuditLog.query.count() == before + 1

    db.session.rollback()
    assert AuditLog.query.count() == before
