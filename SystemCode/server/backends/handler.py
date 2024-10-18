import os
import re
import uuid
import urllib
import asyncio
import logging
from datetime import datetime

from sanic.response import ResponseStream
from sanic.response import json as sanic_json
from sanic.response import text as sanic_text
from sanic import request as sanic_request

from SystemCode.configs.database import CONNECT_MODE
from SystemCode.configs.basic import *
# from SystemCode.core.file import File
from SystemCode.utils.general_utils import *
from SystemCode.connector.database.mysql_client import MySQLClient


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# init Mysql client
mysql_client = MySQLClient(CONNECT_MODE)


def init_folders():
    """
    init the necessary folders
    :return:
    """
    if not os.path.exists(DATA_PATH):
        os.makedirs(DATA_PATH)

    if not os.path.exists(FILES_PATH):
        os.makedirs(FILES_PATH)

    if not os.path.exists(MODEL_PATH):
        os.makedirs(MODEL_PATH)


async def new_knowledge_base(req: sanic_request):
    """
    user_id, new_kb_name
    create new knowledge base for user, insert into milvus, mysql
    """
    # input
    user_id = safe_get(req, 'user_id')
    if type(user_id) == list:
        user_id = user_id[0]

    logging.info("[API]-[new knowledge base] user_id: %s", user_id)
    if user_id is None:
        return sanic_json({"code": 2002, "msg": f'[user_id]输入非法！request.json：{req.json}，请检查！'})
    is_valid = validate_user_id(user_id)
    if not is_valid:
        return sanic_json({"code": 2005, "msg": get_invalid_user_id_msg(user_id=user_id)})
    logging.info("new_knowledge_base %s", user_id)

    kb_name = safe_get(req, 'kb_name')
    if kb_name is None:
        return sanic_json({"code": 2002, "msg": f'[kb_name]输入非法！request.json：{req.json}，请检查！'})

    # check
    existing_kb = mysql_client.check_kb_exist_by_name(user_id, kb_name)
    if existing_kb:
        return sanic_json({"code": 2006, "msg": f'知识库名称 "{kb_name}" 已经存在，请使用不同的名称！'})

    # generate
    kb_id = 'KB' + uuid.uuid4().hex

    mysql_client.create_milvus_collection(kb_id, user_id, kb_name)
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d%H%M")
    return sanic_json({"code": 200, "msg": "success create knowledge base {}".format(kb_id),
                       "data": {"kb_id": kb_id, "kb_name": kb_name, "timestamp": timestamp}})


async def list_knowledge_base(req: sanic_request):
    """
    user_id
    :param req:
    :return:
    """
    user_id = safe_get(req, 'user_id')
    if type(user_id) == list:
        user_id = user_id[0]

    logging.info("[API]-[list knowledge base] user_id: %s", user_id)
    if user_id is None:
        return sanic_json({"code": 2002, "msg": f'[user_id]输入非法！request.json：{req.json}，请检查！'})
    is_valid = validate_user_id(user_id)
    if not is_valid:
        return sanic_json({"code": 2005, "msg": get_invalid_user_id_msg(user_id=user_id)})

    kbs = mysql_client.list_knowledge_base(user_id)
    return sanic_json({"code": 200, "msg": "success", "data": kbs})


async def delete_knowledge_base(req: sanic_request):
    """
    user_id, kb_id
    delete knowledge base for user, delete from milvus, mysql
    """
    user_id = safe_get(req, 'user_id')
    if type(user_id) == list:
        user_id = user_id[0]

    logging.info("[API]-[delete knowledge base] user_id: %s", user_id)
    if user_id is None:
        return sanic_json({"code": 2002, "msg": f'[user_id]输入非法！request.json：{req.json}，请检查！'})
    is_valid = validate_user_id(user_id)
    if not is_valid:
        return sanic_json({"code": 2005, "msg": get_invalid_user_id_msg(user_id=user_id)})

    kb_id = safe_get(req, 'kb_id')
    if kb_id is None:
        return sanic_json({"code": 2002, "msg": f'[kb_id]输入非法！request.json：{req.json}，请检查！'})

    # validate the kb_id
    invalid_kb_ids = mysql_client.check_kb_exist(user_id, [kb_id])
    if invalid_kb_ids:
        return sanic_json({"code": 2001, "msg": f'invalid kb_id: {invalid_kb_ids}, please check...'})

    mysql_client.delete_knowledge_base(user_id, kb_id)
    return sanic_json({"code": 200, "msg": "success delete knowledge base {}".format(kb_id)})


async def update_knowledge_base_name(req: sanic_request):
    """
    user_id, kb_id, new_kb_name
    update knowledge base name
    """
    user_id = safe_get(req, 'user_id')
    if type(user_id) == list:
        user_id = user_id[0]
    logging.info("[API]-[update knowledge base name] user_id: %s", user_id)
    if user_id is None:
        return sanic_json({"code": 2002, "msg": f'[user_id]输入非法！request.json：{req.json}，请检查！'})
    is_valid = validate_user_id(user_id)
    if not is_valid:
        return sanic_json({"code": 2005, "msg": get_invalid_user_id_msg(user_id=user_id)})

    kb_id = safe_get(req, 'kb_id')
    if kb_id is None:
        return sanic_json({"code": 2002, "msg": f'[kb_id]输入非法！request.json：{req.json}，请检查！'})

    new_kb_name = safe_get(req, 'new_kb_name')
    if new_kb_name is None:
        return sanic_json({"code": 2002, "msg": f'[new_kb_name]输入非法！request.json：{req.json}，请检查'})

    if mysql_client.check_kb_exist_by_name(user_id, new_kb_name):
        return sanic_json({"code": 2001, "msg": f'kb名重复'})

    mysql_client.update_knowledge_base_name(user_id, kb_id, new_kb_name)

    return sanic_json({"code": 200, "msg": "success update knowledge base name"})


# --------------------------- User ---------------------------
async def add_new_user(req: sanic_request):
    """
    user_name
    add new user into mysql
    """
    user_name = safe_get(req, 'user_name')
    if user_name is None:
        return sanic_json({"code": 2002, "msg": f'输入非法！request.json：{req.json}，请检查！'})
    if mysql_client.check_user_exist_by_name(user_name):
        return sanic_json({"code": 2001, "msg": f'用户名{user_name}已存在，请更换！'})
    # generate user_id
    user_id = 'U' + uuid.uuid4().hex

    mysql_client.add_user_(user_id, user_name)
    logging.info("[API]-[add new user] user_id: %s", user_id)
    return sanic_json({"code": 200, "msg": "success add user, id: {}".format(user_id), "user_id":user_id})


async def get_user_id_by_name(req: sanic_request):
    """
    user_name

    get user_id by user_name
    :param req:
    :return:
    """
    user_name = safe_get(req, 'user_name')
    if user_name is None:
        return sanic_json({"code": 2002, "msg": f'输入非法！request.json：{req.json}，请检查！'})

    logging.info("[API]-[get user id by name] user_name: %s", user_name)

    sql = "SELECT user_id FROM User WHERE user_name = %s"
    result = mysql_client.execute_query_(sql, (user_name,), fetch=True)
    if not result:
        return sanic_json({"code": 2001, "msg": f'无法找到用户{user_name}，请检查！'})

    user_id = result[0][0]

    return sanic_json({"code": 200, "msg": "success", "data": {"user_id": user_id}})


async def upload_files(req: sanic_request):
    """
    user_id, kb_id, files, mode
    upload files
    """
    user_id = safe_get(req, 'user_id')
    if user_id is None:
        return sanic_json({"code": 2002, "msg": f'输入非法！request.form: {req.form}，request.files: {req.files}请检查！'})
    is_valid = validate_user_id(user_id)
    if not is_valid:
        return sanic_json({"code": 2005, "msg": get_invalid_user_id_msg(user_id=user_id)})
    logging.info("[API]-[upload file] user_id: %s", user_id)

    kb_id = safe_get(req, 'kb_id')
    kb_id = kb_id[0] if type(kb_id) == list else kb_id
    if kb_id is None:
        return sanic_json({"code": 2002, "msg": f'输入非法！request.json：{req.json}，请检查！'})
    not_exist_kb_ids = mysql_client.check_kb_exist(user_id, [kb_id])
    if not_exist_kb_ids:
        msg = "invalid kb_id: {}, please check...".format(not_exist_kb_ids)
        return sanic_json({"code": 2001, "msg": msg, "data": [{}]})

    mode = safe_get(req, 'mode', default='soft')  # soft代表不上传同名文件，strong表示强制上传同名文件
    logging.info("mode: %s", mode)
    use_local_file = safe_get(req, 'use_local_file', 'false')
    if use_local_file == 'true':
        files = read_files_with_extensions()
    else:
        files = req.files.getlist('files')

    data = []
    local_files = []
    file_names = []
    for file in files:
        if isinstance(file, str):
            file_name = os.path.basename(file)
        else:
            logging.info('ori name: %s', file.name)
            file_name = urllib.parse.unquote(file.name, encoding='UTF-8')
            logging.info('decode name: %s', file_name)
        # 删除掉全角字符
        file_name = re.sub(r'[\uFF01-\uFF5E\u3000-\u303F]', '', file_name)
        file_name = file_name.replace("/", "_")
        logging.info('cleaned name: %s', file_name)
        file_name = truncate_filename(file_name)
        file_names.append(file_name)

    exist_file_names = []
    if mode == 'soft':
        exist_files = mysql_client.check_file_exist_by_name(user_id, kb_id, file_names)
        exist_file_names = [f[1] for f in exist_files]

    now = datetime.now()
    timestamp = now.strftime("%Y%m%d%H%M")

    for file, file_name in zip(files, file_names):
        if file_name in exist_file_names:
            continue
        file_size = len(file.body)
        file_path = os.path.join(FILES_PATH, kb_id, file_name)
        if not os.path.exists(os.path.join(FILES_PATH, kb_id)):
            os.makedirs(os.path.join(FILES_PATH, kb_id))

        # save file
        with open(file_path, 'wb') as f:
            f.write(file.body)

        file_id, msg = mysql_client.add_file(user_id, kb_id, file_name, timestamp, file_size, file_path)
        logging.info(f"{file_name}, {file_id}, {msg}")
        data.append(
            {"file_id": file_id, "file_name": file_name, "status": "waiting", "bytes(KB)": file_size // (8 * 1024),
             "timestamp": timestamp})

    if exist_file_names:
        msg = f'warning，当前的mode是soft，无法上传同名文件{exist_file_names}，如果想强制上传同名文件，请设置mode：strong'
        return sanic_json({"code": 2001, "msg": msg, "data": data})
    else:
        msg = "success，后台正在飞速上传文件，请耐心等待"
        return sanic_json({"code": 200, "msg": msg, "data": data})


async def upload_url(req: sanic_request):
    """
    user_id, kb_id, url
    upload url
    """
    user_id = safe_get(req, 'user_id')
    if user_id is None:
        return sanic_json({"code": 2002, "msg": f'输入非法！request.form: {req.form}，request.files: {req.files}请检查！'})
    is_valid = validate_user_id(user_id)
    if not is_valid:
        return sanic_json({"code": 2005, "msg": get_invalid_user_id_msg(user_id=user_id)})
    logging.info("[API]-[upload file] user_id: %s", user_id)

    kb_id = safe_get(req, 'kb_id')
    kb_id = kb_id[0] if type(kb_id) == list else kb_id
    if kb_id is None:
        return sanic_json({"code": 2002, "msg": f'输入非法！request.json：{req.json}，请检查！'})
    not_exist_kb_ids = mysql_client.check_kb_exist(user_id, [kb_id])
    if not_exist_kb_ids:
        msg = "invalid kb_id: {}, please check...".format(not_exist_kb_ids)
        return sanic_json({"code": 2001, "msg": msg, "data": [{}]})

    mode = safe_get(req, 'mode', default='soft')  # soft代表不上传同名文件，strong表示强制上传同名文件
    logging.info("mode: %s", mode)

    url = safe_get(req, 'url')
    if not url:
        return sanic_json({"code": 2002, "msg": f'输入非法！request.json：{req.json}，请检查！'})

    if mysql_client.check_url_exist(kb_id, url):
        return sanic_json({"code": 2001, "msg": f'当前url已存在，请检查！'})

    now = datetime.now()
    timestamp = now.strftime("%Y%m%d%H%M")
    data = []
    file_id, msg = mysql_client.add_file(user_id, kb_id, url +'.url', timestamp, '-1', url)
    logging.info(f"{url}, {file_id}, {msg}")
    data.append(
        {"file_id": file_id, "file_name": url + '.url', "status": "waiting", "bytes(KB)": '-1',
         "timestamp": timestamp})

    msg = "success，链接加载中，请耐心等待"
    return sanic_json({"code": 200, "msg": msg, "data": data})


async def check_file_list(req: sanic_request):
    """
    user_id, kb_id
    check file list
    """
    user_id = safe_get(req, 'user_id')
    if user_id is None:
        return sanic_json({"code": 2002, "msg": f'输入非法！request.json：{req.json}，请检查！'})
    is_valid = validate_user_id(user_id)
    if not is_valid:
        return sanic_json({"code": 2005, "msg": get_invalid_user_id_msg(user_id=user_id)})
    logging.info("[API]-[check file list] user_id: %s", user_id)

    kb_id = safe_get(req, 'kb_id')
    kb_id = kb_id[0] if type(kb_id) == list else kb_id
    if kb_id is None:
        return sanic_json({"code": 2002, "msg": f'输入非法！request.json：{req.json}，请检查！'})
    not_exist_kb_ids = mysql_client.check_kb_exist(user_id, [kb_id])
    if not_exist_kb_ids:
        msg = "invalid kb_id: {}, please check...".format(not_exist_kb_ids)
        return sanic_json({"code": 2001, "msg": msg, "data": [{}]})

    files = mysql_client.select_file_list_by_kb_id(kb_id)
    return sanic_json({"code": 200, "msg": "success", "data": files})


async def delete_file(req: sanic_request):
    """
    user_id, kb_id，file_id
    delete file
    """
    user_id = safe_get(req, 'user_id')
    if user_id is None:
        return sanic_json({"code": 2002, "msg": f'输入非法！request.json：{req.json}，请检查！'})
    is_valid = validate_user_id(user_id)
    if not is_valid:
        return sanic_json({"code": 2005, "msg": get_invalid_user_id_msg(user_id=user_id)})
    logging.info("[API]-[delete file] user_id: %s", user_id)

    kb_id = safe_get(req, 'kb_id')
    kb_id = kb_id[0] if type(kb_id) == list else kb_id
    if kb_id is None:
        return sanic_json({"code": 2002, "msg": f'输入非法！request.json：{req.json}，请检查！'})
    not_exist_kb_ids = mysql_client.check_kb_exist(user_id, [kb_id])
    if not_exist_kb_ids:
        msg = "invalid kb_id: {}, please check...".format(not_exist_kb_ids)
        return sanic_json({"code": 2001, "msg": msg, "data": [{}]})

    file_id = safe_get(req, 'file_id')
    if file_id is None:
        return sanic_json({"code": 2002, "msg": f'输入非法！request.json：{req.json}，请检查！'})

    mysql_client.delete_file(user_id, kb_id, file_id)
    return sanic_json({"code": 200, "msg": "success delete file"})


async def update_user_name(req: sanic_request):
    """
    user_name
    user_id
    new_user_name
    update new username
    """
    user_id = safe_get(req, 'user_id')
    if user_id is None:
        return sanic_json({"code": 2002, "msg": f'输入非法！request.json：{req.json}，请检查！'})
    is_valid = validate_user_id(user_id)
    if not is_valid:
        return sanic_json({"code": 2005, "msg": get_invalid_user_id_msg(user_id=user_id)})
    logging.info("[API]-[update user name] user_id: %s", user_id)

    user_name = safe_get(req, 'user_name')
    if not user_name:
        return sanic_json({"code": 2002, "msg": f'输入非法！request.json：{req.json}，请检查！'})
    if not mysql_client.match_user_name_and_id(user_id, user_name):
        return sanic_json({"code": 2001, "msg": f'用户名信息bu匹配，请检查用户名！'})

    new_user_name = safe_get(req, 'new_user_name')
    if new_user_name is None:
        return sanic_json({"code": 2002, "msg": f'输入非法！request.json：{req.json}，请检查！'})

    if mysql_client.check_user_exist_by_name(new_user_name):
        return sanic_json({"code": 2001, "msg": f'用户名{new_user_name}已存在，请更换！'})

    mysql_client.update_user_name(user_id, user_name, new_user_name)

    return sanic_json({"code": 200, "msg": "success update user name"})


async def login(req: sanic_request):
    """
    user_name
    log in
    """
    user_name = safe_get(req, 'user_name')
    if user_name is None:
        return sanic_json({"code": 2002, "msg": f'输入非法！request.json：{req.json}，请检查！'})

    status = mysql_client.check_user_exist_by_name(user_name)
    if not status:
        return sanic_json({"code": 200, "msg": f'用户名不存在，请检查！', "status": False})

    sql = "SELECT user_id FROM User WHERE user_name = %s"
    result = mysql_client.execute_query_(sql, (user_name,), fetch=True)
    user_id = result[0][0]

    logging.info("[API]-[login] user_id: %s", user_id)
    return sanic_json({"code": 200, "msg": "success log in", "status": True, "user_id": user_id})