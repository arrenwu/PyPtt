import time

from . import _api_set_board_title
from . import _api_util
from . import check_value
from . import command
from . import exceptions
from . import i18n
from . import lib_util
from . import screens
from ._api_set_board_title import step

from functools import wraps


def _bucket_days_max() -> int:
    # pttbbs mbbsd/acl.c:180-206: 期限輸入欄 getdata(..., datebuf, 8) 最多 7 位數，
    # 到期時間用 time4_add_sec() 算，超過 0xFFFFFFFF (2106-02-07) 就回「日期過大」
    # (include/cmsys.h:86-93)。所以上限是「現在到 2106-02-07」的整天數。
    return min(9999999, (0xFFFFFFFF - int(time.time())) // 86400 - 1)

from .data_type import UserField

import re

def _bucket_days_max() -> int:
    # pttbbs mbbsd/acl.c:180-206: 期限輸入欄 getdata(..., datebuf, 8) 最多 7 位數，
    # 到期時間用 time4_add_sec() 算，超過 0xFFFFFFFF (2106-02-07) 就回「日期過大」
    # (include/cmsys.h:86-93)。所以上限是「現在到 2106-02-07」的整天數。
    return min(9999999, (0xFFFFFFFF - int(time.time())) // 86400 - 1)


def bucket(api, board: str, bucket_days: int, reason: str, ptt_id: str) -> None:
    _api_util.one_thread(api)

    if not api._is_login:
        raise exceptions.RequireLogin(i18n.require_login)

    if not api.is_registered_user:
        raise exceptions.UnregisteredUser(lib_util.get_current_func_name())

    check_value.check_type(board, str, 'board')
    check_value.check_type(bucket_days, int, 'bucket_days')
    check_value.check_type(reason, str, 'reason')
    check_value.check_type(ptt_id, str, 'ptt_id')
    # bool 是 int 的子類別；期限要是正整數天，且不超過 PTT 能存的到期時間
    max_days = _bucket_days_max()
    if isinstance(bucket_days, bool) or not 0 < bucket_days <= max_days:
        raise exceptions.ParameterError(f'bucket_days must be an int in 1..{max_days}, got {bucket_days!r}')
    _api_util.check_no_control_chars(reason, 'reason')
    _api_util.check_no_control_chars(ptt_id, 'ptt_id')

    _api_util.check_user_exist(api, ptt_id)

    _api_util.check_board(api, board, check_moderator=True)

    _api_util.goto_board(api, board)

    # 從這裡起進入看板設定；任何結束路徑都由 run_in_board_setting 退回文章列表
    _api_util.run_in_board_setting(api, lambda: _bucket_in_board_setting(api, board, bucket_days, reason, ptt_id))


def _bucket_in_board_setting(api, board: str, bucket_days: int, reason: str, ptt_id: str) -> None:

    # 新版編輯模式裡 w 直接打開 Bakuman (不能再補 Enter，Enter 會被當成 [Q]結束)；
    # 舊版 w 是「請輸入要改變的設定」單行輸入，要 Enter 送出。
    mode = _api_set_board_title.open_board_setting(api, board, 'i')
    step(api, 'w' if mode == 'new' else 'w' + command.enter, [('bakuman', screens.Target.Bakuman)])

    # Bakuman 新舊版相同，每一步都比對提示再送下一步
    step(api, 'a' + command.enter, [('id', '請輸入使用者代號')])
    result = step(api, ptt_id + command.enter, [
        ('period', '請以數字跟單位(預設為天)輸入期限'),
        ('banned', '◆ 使用者之前已被禁言'),
    ])
    if result == 'banned':
        raise exceptions.UserHasPreviouslyBeenBanned()

    step(api, str(bucket_days) + command.enter, [('reason', '請輸入理由')])
    step(api, reason + command.enter, [('confirm', '確認以上資料全部正確嗎')])
    step(api, 'y' + command.enter, [
        ('done', '◆ 已將使用者加入禁言名單'),
    ], screen_timeout=api.config.screen_long_timeout)

    # [按任意鍵繼續] → 回到 [Q]結束? → Enter (空白 = Q) 離開 Bakuman
    step(api, command.left, [('bakuman', screens.Target.Bakuman)])
    if mode == 'new':
        step(api, command.enter, [('edit', screens.Target.BoardSettingEdit)])
    else:
        step(api, command.enter, [('prompt', screens.Target.BoardSettingOldPrompt)])

    _api_set_board_title.close_board_setting(api, mode)

def bakuman(func):
    """
    This is the decorator for the action which performs the operations in the Bakuman menu.
    Please make sure for the decorated function,
        - the first argument is the api object.
        - the second argument is the board name.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Please make sure for the decorated function,
        # the first argument is the api object.
        # the second argument is the board name.
        api = args[0]
        board = args[1]

        # 新版編輯模式裡 w 直接打開 Bakuman (不能再補 Enter，Enter 會被當成 [Q]結束)；
        # 舊版 w 是「請輸入要改變的設定」單行輸入，要 Enter 送出。
        mode = _api_set_board_title.open_board_setting(api, board, 'i')
        step(api, 'w' if mode == 'new' else 'w' + command.enter, [('bakuman', screens.Target.Bakuman)])

        # 執行Bakuman指令
        result = func(*args, **kwargs)

        # [按任意鍵繼續] → 回到 [Q]結束? → Enter (空白 = Q) 離開 Bakuman
        step(api, command.left, [('bakuman', screens.Target.Bakuman)])
        if mode == 'new':
            step(api, command.enter, [('edit', screens.Target.BoardSettingEdit)])
        else:
            step(api, command.enter, [('prompt', screens.Target.BoardSettingOldPrompt)])

        _api_set_board_title.close_board_setting(api, mode)

        return result
    return wrapper

# def my_decorator(func):
#     @wraps(func)
#     def wrapper(*args, **kwargs):
#         # Access the decorated function's arguments
#         print("Positional arguments:", args)
#         print("Keyword arguments:", kwargs)

#         # Use an argument in your own logic
#         if args and args[0] > 0:
#             print("First argument is positive")

#         return func(*args, **kwargs)

#     return wrapper

# What I added

@bakuman
def _lift_bucket(api, board: str, ptt_id: str, reason: str) -> None:
    """提前解除水桶

    Args:
        api (_type_): _description_
        board (str): 板名
        ptt_id (str): ptt_id
        reason: 解除水桶裡由
    """
    step(api, 'd' + command.enter, [('id', '請輸入使用者代號')])
    result = step(api, ptt_id + command.enter, [
        ('reason', '請輸入理由'),
        ('not_banned', '◆ 使用者目前不在禁言名單中'),
    ])
    if result == 'not_banned':
        raise exceptions.UserNotInBanList()

    step(api, reason + command.enter, [('confirm', '確認以上資料全部正確嗎')])
    step(api, 'y' + command.enter, [
        ('done', '使用者的禁言限制已解除'),
    ], screen_timeout=api.config.screen_long_timeout)


def lift_bucket(api, board: str, ptt_id: str, reason: str) -> None:
    """提前解除水桶

    Args:
        api (_type_): _description_
        board (str): 板名
        ptt_id (str): ptt_id
        reason: 解除水桶裡由
    """
    _api_util.run_in_board_setting(api, lambda: _lift_bucket(api, board, ptt_id, reason))

@bakuman
def _get_bucket_status(api, board: str, ptt_id: str):
    """取得使用者水桶狀態

    Args:
        api (_type_): _description_
        board (str): 板名
        ptt_id (str): ptt_id

    Returns:
        dict: {
            'is_suspended' : bool
            'remaining_days' : int
        }
    """
    step(api, 's' + command.enter, [('id', '請輸入使用者代號')])
    result = step(api, ptt_id + command.enter, [
        ('not_suspended', '目前不在禁言名單中'),
        ('suspended', '解除時間尚有'),
    ])
    if result == 'not_suspended':
        return { UserField.is_suspended   : False,
                 UserField.remaining_days : 0}
    else:
        # 解析解除時間尚有 N 天
        last_screen = api.connect_core.get_screen_queue()[-1]
        match = re.search(r'解除時間尚有 *(?P<days>\d+) *天', last_screen)
        if match is None:
            raise exceptions.UnknownError(f'Failed to parse remaining days from screen:\n{last_screen}')
        remaining_days = int(match.group('days'))
        return { UserField.is_suspended   : True,
                 UserField.remaining_days : remaining_days}

def get_bucket_status(api, board: str, ptt_id: str):
    """ 取得使用者水桶狀態

    Args:
        board (str): 板名
        ptt_id (str): ptt_id

    Returns:
        dict: {
            'is_suspended' : bool
            'remaining_days' : int
        }
    """

    return _api_util.run_in_board_setting(api, lambda: _get_bucket_status(api, board, ptt_id))


def moderator_operation_reset(api, board: str, ptt_id: str):
    """
    1. Confirm api login and the user is a moderator of the board.
    2. Confirm the existence of ptt_id
    3. goto the board where the user is to be suspended.
    """
    check_value.check_type(board, str, 'board')
    check_value.check_type(ptt_id, str, 'ptt_id')

    # Confirm single thread
    _api_util.one_thread(api)

    # Confirm login status
    if not api._is_login:
        raise exceptions.RequireLogin(i18n.require_login)

    # Confirm the user is registered
    if not api.is_registered_user:
        raise exceptions.UnregisteredUser(lib_util.get_current_func_name())

    check_value.check_type(board, str, 'board')

    check_value.check_type(ptt_id, str, 'ptt_id')

    _api_util.check_no_control_chars(ptt_id, 'ptt_id')

    _api_util.check_user_exist(api, ptt_id)

    # Confirm moderator status
    _api_util.check_board(api, board, check_moderator=True)

    # Move cursor to the board
    _api_util.goto_board(api, board)
