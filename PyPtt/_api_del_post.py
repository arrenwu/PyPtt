from __future__ import annotations

from tkinter import E
from typing import Optional

from . import _api_util, _api_bucket
from . import check_value
from . import command
from . import connect_core
from . import data_type
from . import exceptions
from . import i18n
from . import lib_util
from . import log
from . import screens

def recycle_post_to_mailbox(api, board: str, post_aid: str, ptt_id: str):
    # Go to the board and confirm moderator identity
    _api_bucket.moderator_operation_reset(api, board, ptt_id)

    # Get into the recycle bin
    cmd_list = []
    cmd_list.append(command.tilde)

    cmd = ''.join(cmd_list)

    target_list = [
        connect_core.TargetUnit('Magical Index: 編輯歷史', response=command.tilde),
        connect_core.TargetUnit('此篇文章暫無編輯歷史記錄', response=command.tilde),
        connect_core.TargetUnit('站方不保證此處為完整的電磁記錄', response=command.space),
        connect_core.TargetUnit('請按任意鍵繼續', response=command.space),

        # Desired destination
        connect_core.TargetUnit('已刪檔案', break_detect=True),

        # No articles in the recycle bin.
        connect_core.TargetUnit(screens.Target.InBoard, exceptions_=exceptions.NoSuchPost(board, post_aid)),
    ]

    index = api.connect_core.send(
    cmd,
    target_list)
    assert index >= 0, "index= {}. TargetUnit was not found".format(index)

    # TODO: Issue #265
    # Shouldn't have to do this. Need to find out the cause.
    _api_util.goto_board(api, board)

    index = api.connect_core.send(
    cmd,
    target_list)
    assert index >= 0, "index= {}. TargetUnit was not found".format(index)

    # Go to the index
    cmd_list2 = []
    cmd_list2.append('#{}'.format(post_aid))
    cmd_list2.append(command.enter)

    cmd2 = ''.join(cmd_list2)

    target_list2  = [
        connect_core.TargetUnit(['Magical Index: 資源回收筒', '找不到符合的資料'], exceptions_=exceptions.NoSuchPost(board, post_aid)),
        connect_core.TargetUnit('已刪檔案', break_detect=True),
    ]

    index = api.connect_core.send(
    cmd2,
    target_list2)
    assert index >= 0, "index= {}. TargetUnit was not found".format(index)

    # Go to the index
    cmd_list3 = []
    cmd_list3.append('x')

    cmd3 = ''.join(cmd_list3)

    target_list3  = [
        connect_core.TargetUnit('儲存完成，請至信箱檢查備忘錄信件', response=command.space, break_detect=True), # This must be the first line
        connect_core.TargetUnit('確定要把此份文件回存至信箱嗎', response=''.join(['y', command.enter])),
    ]

    index = api.connect_core.send(
    cmd3,
    target_list3)
    assert index >= 0, "index= {}. TargetUnit was not found".format(index)

def del_post(api, board: str, post_aid: Optional[str] = None, post_index: int = 0) -> None:
    _api_util.one_thread(api)

    if not api.is_registered_user:
        raise exceptions.UnregisteredUser(lib_util.get_current_func_name())

    if not api._is_login:
        raise exceptions.RequireLogin(i18n.require_login)

    check_value.check_type(board, str, 'board')
    if post_aid is not None:
        check_value.check_type(post_aid, str, 'PostAID')
    check_value.check_type(post_index, int, 'PostIndex')

    if len(board) == 0:
        raise ValueError(f'board error parameter: {board}')

    if post_index != 0 and isinstance(post_aid, str):
        raise ValueError('wrong parameter index and aid can\'t both input')

    if post_index == 0 and post_aid is None:
        raise ValueError('wrong parameter index or aid must input')

    if post_index != 0:
        newest_index = api.get_newest_index(
            data_type.NewIndex.BOARD,
            board=board)
        check_value.check_index(
            'PostIndex',
            post_index,
            newest_index)

    log.logger.info(i18n.delete_post)

    board_info = _api_util.check_board(api, board)

    check_author = True
    for moderator in board_info[data_type.BoardField.moderators]:
        if api.ptt_id.lower() == moderator.lower():
            check_author = False
            break

    log.logger.info(i18n.delete_post)

    post_info = api.get_post(board, aid=post_aid, index=post_index, query=True)
    if post_info[data_type.PostField.post_status] != data_type.PostStatus.EXISTS:
        # delete success
        log.logger.info(i18n.delete_post, '...', i18n.success)
        return

    if check_author:
        if api.ptt_id.lower() != post_info[data_type.PostField.author].lower():
            log.logger.info(i18n.delete_post, '...', i18n.fail)
            raise exceptions.NoPermission(i18n.no_permission)

    _api_util.goto_board(api, board)

    cmd_list = []

    if post_aid is not None:
        cmd_list.append(lib_util.check_aid(post_aid))
    elif post_index != 0:
        cmd_list.append(str(post_index))
    else:
        raise ValueError('post_aid and post_index cannot be None at the same time')

    cmd_list.append(command.enter)
    cmd_list.append('d')

    cmd = ''.join(cmd_list)

    api.confirm = False

    def confirm_delete_handler(screen):
        api.confirm = True

    target_list = [
        connect_core.TargetUnit('請按任意鍵繼續', response=' '),
        connect_core.TargetUnit('請確定刪除(Y/N)?[N]', response='y' + command.enter, handler=confirm_delete_handler,
                                max_match=1),
        connect_core.TargetUnit(screens.Target.InBoard, break_detect=True),
    ]

    index = api.connect_core.send(
        cmd,
        target_list)

    if index == 1:
        if not api.confirm:
            log.logger.info(i18n.delete_post, '...', i18n.fail)
            raise exceptions.NoPermission(i18n.no_permission)

    log.logger.info(i18n.delete_post, '...', i18n.success)
