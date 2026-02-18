from ..models import Break, Shift


class OpenShiftNotFoundError(LookupError):
    """Raised when the user has no open shift."""


class OpenBreakNotFoundError(LookupError):
    """Raised when the shift has no open break."""


def get_open_shift(user_id):
    return Shift.query.filter_by(user_id=user_id, clock_out_at=None).order_by(Shift.id.desc()).first()


def get_open_break(shift_id):
    return Break.query.filter_by(shift_id=shift_id, end_at=None).order_by(Break.id.desc()).first()


def get_open_shift_or_abort(user_id):
    shift = get_open_shift(user_id)
    if not shift:
        raise OpenShiftNotFoundError
    return shift


def get_open_break_or_abort(shift_id):
    br = get_open_break(shift_id)
    if not br:
        raise OpenBreakNotFoundError
    return br
