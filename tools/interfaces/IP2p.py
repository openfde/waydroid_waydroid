import gbinder
import logging
from tools import helpers
from gi.repository import GLib


INTERFACE = "android.openfde.IP2p"
SERVICE_NAME = "openfdep2p"

TRANSACTION_addBonjourService = 1
TRANSACTION_addGroup = 2
TRANSACTION_cancelConnect = 3
TRANSACTION_p2p_stop_find = 4
TRANSACTION_p2p_asp_provision = 5
TRANSACTION_p2p_asp_provision_resp = 6
TRANSACTION_p2p_connect = 7
TRANSACTION_p2p_listen = 8
TRANSACTION_p2p_group_remove = 9
TRANSACTION_p2p_group_member = 10
TRANSACTION_p2p_prov_disc = 11
TRANSACTION_p2p_get_passphrase = 12
TRANSACTION_p2p_serv_disc_req = 13
TRANSACTION_p2p_serv_disc_cancel = 14
TRANSACTION_p2p_serv_disc_resp = 15
TRANSACTION_p2p_service_update = 16
TRANSACTION_p2p_serv_disc_external = 17
TRANSACTION_p2p_service_flush = 18
TRANSACTION_p2p_service_rep = 19
TRANSACTION_p2p_service_del = 20
TRANSACTION_p2p_reject = 21
TRANSACTION_p2p_invite = 22
TRANSACTION_p2p_peers = 23
TRANSACTION_p2p_peer = 24
TRANSACTION_p2p_set = 25
TRANSACTION_p2p_flush = 26
TRANSACTION_p2p_unauthorize = 27
TRANSACTION_p2p_presence_req = 28
TRANSACTION_p2p_ext_listen = 29
TRANSACTION_p2p_remove_client = 30


def _read_byte_array(reader):
    for method_name in ("read_buffer", "read_bytes", "read_byte_array", "read_blob"):
        if hasattr(reader, method_name):
            value = getattr(reader, method_name)()
            if value is None:
                return None
            if isinstance(value, (bytes, bytearray)):
                return bytes(value)
            if hasattr(value, "tobytes"):
                return value.tobytes()
            return value
    return None


def _read_string16(reader):
    try:
        return reader.read_string16()
    except Exception:
        return ""


def add_service(
    args,
    addBonjourService,
    addGroup,
    cancelConnect,
    p2p_stop_find,
    p2p_asp_provision,
    p2p_asp_provision_resp,
    p2p_connect,
    p2p_listen,
    p2p_group_remove,
    p2p_group_member,
    p2p_prov_disc,
    p2p_get_passphrase,
    p2p_serv_disc_req,
    p2p_serv_disc_cancel,
    p2p_serv_disc_resp,
    p2p_service_update,
    p2p_serv_disc_external,
    p2p_service_flush,
    p2p_service_rep,
    p2p_service_del,
    p2p_reject,
    p2p_invite,
    p2p_peers,
    p2p_peer,
    p2p_set,
    p2p_flush,
    p2p_unauthorize,
    p2p_presence_req,
    p2p_ext_listen,
    p2p_remove_client,
):
    helpers.drivers.loadBinderNodes(args)
    try:
        serviceManager = gbinder.ServiceManager("/dev/" + args.BINDER_DRIVER, args.SERVICE_MANAGER_PROTOCOL, args.BINDER_PROTOCOL)
    except TypeError:
        serviceManager = gbinder.ServiceManager("/dev/" + args.BINDER_DRIVER)

    def response_handler(req, code, flags):
        logging.debug(
            "{}: Received transaction: {}".format(SERVICE_NAME, code))
        reader = req.init_reader()
        local_response = response.new_reply()

        if code == TRANSACTION_addBonjourService:
            query = _read_byte_array(reader)
            response_data = _read_byte_array(reader)
            addBonjourService(query, response_data)
            local_response.append_int32(0)
        elif code == TRANSACTION_addGroup:
            status, persistent = reader.read_int32()
            status, persistentNetworkId = reader.read_int32()
            addGroup(persistent != 0, persistentNetworkId)
            local_response.append_int32(0)
        elif code == TRANSACTION_cancelConnect:
            cancelConnect()
            local_response.append_int32(0)
        elif code == TRANSACTION_p2p_stop_find:
            p2p_stop_find()
            local_response.append_int32(0)
        elif code == TRANSACTION_p2p_asp_provision:
            p2p_asp_provision(_read_string16(reader))
            local_response.append_int32(0)
        elif code == TRANSACTION_p2p_asp_provision_resp:
            p2p_asp_provision_resp(_read_string16(reader))
            local_response.append_int32(0)
        elif code == TRANSACTION_p2p_connect:
            p2p_connect(_read_string16(reader))
            local_response.append_int32(0)
        elif code == TRANSACTION_p2p_listen:
            p2p_listen(_read_string16(reader))
            local_response.append_int32(0)
        elif code == TRANSACTION_p2p_group_remove:
            p2p_group_remove(_read_string16(reader))
            local_response.append_int32(0)
        elif code == TRANSACTION_p2p_group_member:
            p2p_group_member(_read_string16(reader))
            local_response.append_int32(0)
        elif code == TRANSACTION_p2p_prov_disc:
            p2p_prov_disc(_read_string16(reader))
            local_response.append_int32(0)
        elif code == TRANSACTION_p2p_get_passphrase:
            ret = p2p_get_passphrase()
            local_response.append_int32(0)
            local_response.append_string16(ret if ret else "")
        elif code == TRANSACTION_p2p_serv_disc_req:
            ret = p2p_serv_disc_req(_read_string16(reader))
            local_response.append_int32(0)
            local_response.append_string16(ret if ret else "")
        elif code == TRANSACTION_p2p_serv_disc_cancel:
            p2p_serv_disc_cancel(_read_string16(reader))
            local_response.append_int32(0)
        elif code == TRANSACTION_p2p_serv_disc_resp:
            p2p_serv_disc_resp(_read_string16(reader))
            local_response.append_int32(0)
        elif code == TRANSACTION_p2p_service_update:
            p2p_service_update()
            local_response.append_int32(0)
        elif code == TRANSACTION_p2p_serv_disc_external:
            p2p_serv_disc_external(_read_string16(reader))
            local_response.append_int32(0)
        elif code == TRANSACTION_p2p_service_flush:
            p2p_service_flush()
            local_response.append_int32(0)
        elif code == TRANSACTION_p2p_service_rep:
            p2p_service_rep(_read_string16(reader))
            local_response.append_int32(0)
        elif code == TRANSACTION_p2p_service_del:
            p2p_service_del(_read_string16(reader))
            local_response.append_int32(0)
        elif code == TRANSACTION_p2p_reject:
            p2p_reject(_read_string16(reader))
            local_response.append_int32(0)
        elif code == TRANSACTION_p2p_invite:
            p2p_invite(_read_string16(reader))
            local_response.append_int32(0)
        elif code == TRANSACTION_p2p_peers:
            ret = p2p_peers()
            local_response.append_int32(0)
            local_response.append_string16(ret if ret else "")
        elif code == TRANSACTION_p2p_peer:
            ret = p2p_peer(_read_string16(reader))
            local_response.append_int32(0)
            local_response.append_string16(ret if ret else "")
        elif code == TRANSACTION_p2p_set:
            p2p_set(_read_string16(reader))
            local_response.append_int32(0)
        elif code == TRANSACTION_p2p_flush:
            p2p_flush()
            local_response.append_int32(0)
        elif code == TRANSACTION_p2p_unauthorize:
            p2p_unauthorize(_read_string16(reader))
            local_response.append_int32(0)
        elif code == TRANSACTION_p2p_presence_req:
            p2p_presence_req(_read_string16(reader))
            local_response.append_int32(0)
        elif code == TRANSACTION_p2p_ext_listen:
            p2p_ext_listen(_read_string16(reader))
            local_response.append_int32(0)
        elif code == TRANSACTION_p2p_remove_client:
            p2p_remove_client(_read_string16(reader))
            local_response.append_int32(0)
        else:
            logging.error("{} unknown code: {}".format(INTERFACE, code))
            local_response.append_int32(0)
            local_response.append_int32(0)

        return local_response, 0

    def binder_presence():
        if serviceManager.is_present():
            status = serviceManager.add_service_sync(SERVICE_NAME, response)

            if status:
                logging.error("Failed to add service {}: {}".format(
                    SERVICE_NAME, status))
                args.p2pLoop.quit()

    response = serviceManager.new_local_object(INTERFACE, response_handler)
    args.p2pLoop = GLib.MainLoop()
    binder_presence()
    status = serviceManager.add_presence_handler(binder_presence)
    if status:
        args.p2pLoop.run()
        serviceManager.remove_handler(status)
        del serviceManager
    else:
        logging.error("Failed to add presence handler: {}".format(status))