from flask import abort

from ..models import Break, Shift


def get_open_shift_or_abort(user_id):
    shift = Shift.query.filter_by(user_id=user_id, clock_out_at=None).order_by(Shift.id.desc()).first()
    if not shift:
        abort(400, "現在、出勤中の記録はありません。")
    return shift


def get_open_break_or_abort(shift_id):
    br = Break.query.filter_by(shift_id=shift_id, end_at=None).order_by(Break.id.desc()).first()
    if not br:
        abort(400, "現在、休憩中の記録はありません。")
    return br
