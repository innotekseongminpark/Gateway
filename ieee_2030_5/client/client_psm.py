from __future__ import annotations

import time
import atexit
import http
import logging
import ssl
import threading
import xml.dom.minidom
from http.client import HTTPSConnection
from os import PathLike
from pathlib import Path
from threading import Timer
from typing import Dict, Optional, Tuple, Any

import werkzeug.middleware.lint
import xsdata
import os, sys
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
sys.path.append(os.path.abspath(r'../COMM'))
sys.path.append(os.path.abspath(r'../TEST'))
sys.dont_write_bytecode = True
import traceback
import GLOBAL
from COMM.Comm_Common import *
from Test_Common import *
import Test_Common

import ieee_2030_5.models as m
from ieee_2030_5.models.constants import UomType
import ieee_2030_5.utils as utils
import ieee_2030_5.utils.tls_wrapper as tls



from ctypes import *
import time

#import numpy as np
#import pandas as pd
import msvcrt

_log = logging.getLogger(__name__)
_log_req_resp = logging.getLogger(__name__ + ".request")


class IEEE2030_5_Client:
    clients: set[IEEE2030_5_Client] = set()

    # noinspection PyUnresolvedReferences
    def __init__(self,
                 cafile: PathLike,
                 server_hostname: str,
                 keyfile: PathLike,
                 certfile: PathLike,
                 server_ssl_port: Optional[int] = 443,
                 debug: bool = True):

        cafile = cafile if isinstance(cafile, PathLike) else Path(cafile)
        keyfile = keyfile if isinstance(keyfile, PathLike) else Path(keyfile)
        certfile = certfile if isinstance(certfile, PathLike) else Path(certfile)

        self._key = keyfile
        self._cert = certfile
        self._ca = cafile

        assert cafile.exists(), f"cafile doesn't exist ({cafile})"
        assert keyfile.exists(), f"keyfile doesn't exist ({keyfile})"
        assert certfile.exists(), f"certfile doesn't exist ({certfile})"

        self._ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)  # ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        self._ssl_context.load_verify_locations(cafile=cafile)
        self._ssl_context.load_cert_chain(certfile=certfile, keyfile=keyfile)
        self._ssl_context.verify_mode = ssl.CERT_REQUIRED
        self._ssl_context.check_hostname = False  # certificate verify failed: IP address mismatch, certificate is not valid for '127.0.0.1'. (_ssl.c:1125)

        with open(cafile, "r") as f:
            for line in f:
                print(line, end="")
            f.close()
            print("\n")
        self._http_conn = HTTPSConnection(host=server_hostname,
                                          port=server_ssl_port,
                                          context=self._ssl_context)
        self._device_cap: Optional[m.DeviceCapability] = None
        self._mup: Optional[m.MirrorUsagePointList] = None
        self._upt: Optional[m.UsagePointList] = None
        self._edev: Optional[m.EndDeviceListLink] = None
        self._end_devices: Optional[m.EndDeviceListLink] = None
        self._fsa_list: Optional[m.FunctionSetAssignmentsListLink] = None
        self._debug = debug
        self._dcap_poll_rate: int = 0
        self._dcap_timer: Optional[Timer] = None
        self._disconnect: bool = False
        self._tls = tls.OpensslWrapper

        IEEE2030_5_Client.clients.add(self)

    @property
    def http_conn(self) -> HTTPSConnection:
        if self._http_conn.sock is None:
            self._http_conn.connect()
        return self._http_conn

    def register_end_device(self) -> str:
        lfid = utils.get_lfdi_from_cert(self._cert)
        sfid = utils.get_sfdi_from_lfdi(lfid)
        response = self.__post__(dcap.EndDeviceListLink.href,
                                 data=utils.dataclass_to_xml(m.EndDevice(sFDI=sfid)))
        print(response)

        if response.status in (200, 201):
            return response.headers.get("Location")

        raise werkzeug.exceptions.Forbidden()

    def get(self, href):
        return self.__get_request__(href)

    def is_end_device_registered(self, end_device: m.EndDevice, pin: int) -> bool:
        reg = self.registration(end_device)
        return reg.pIN == pin

    def new_uuid(self, url: str = "/uuid") -> str:
        res = self.__get_request__(url)
        return res

    def end_devices(self) -> m.EndDeviceList:
        if not self._device_cap:
            self.device_capability()

        self._end_devices = self.__get_request__(self._device_cap.EndDeviceListLink.href)
        return self._end_devices

    def end_device(self, index: Optional[int] = 0) -> m.EndDevice:
        if not self._end_devices:
            self.end_devices()

        return self._end_devices.EndDevice[index]

    def self_device(self) -> m.EndDevice:
        if not self._device_cap:
            self.device_capability()

        return self.__get_request__(self._device_cap.SelfDeviceLink.href)

    def function_set_assignment_list(self,
                                     edev_index: Optional[int] = 0
                                     ) -> m.FunctionSetAssignmentsList:
        fsa_list = self.__get_request__(
            self.end_device(edev_index).FunctionSetAssignmentsListLink.href)
        return fsa_list

    def function_set_assignment(self,
                                edev_index: Optional[int] = 0,
                                fsa_index: Optional[int] = 0) -> m.FunctionSetAssignments:
        fsa_list = self.function_set_assignment_list(edev_index)
        return fsa_list.FunctionSetAssignments[fsa_index]

    def der_list(self, edev_index: Optional[int] = 0) -> m.DERList:
        der_list = self.__get_request__(self.end_device(edev_index).DERListLink.href)
        return der_list

    def poll_timer(self, fn, args):
        if not self._disconnect:
            _log.debug(threading.currentThread().name)
            fn(args)
            threading.currentThread().join()

    def device_capability(self, url: str = "/dcap") -> m.DeviceCapability:
        self._device_cap: m.DeviceCapability = self.__get_request__(url)
        if self._device_cap.pollRate is not None:
            self._dcap_poll_rate = self._device_cap.pollRate
        else:
            self._dcap_poll_rate = 600

        _log.debug(f"devcap id {id(self._device_cap)}")
        _log.debug(threading.currentThread().name)
        _log.debug(f"DCAP: Poll rate: {self._dcap_poll_rate}")
        # self._dcap_timer = Timer(self._dcap_poll_rate, self.poll_timer, (self.device_capability, url))
        # self._dcap_timer.start()
        return self._device_cap

    def time(self) -> m.Time:
        timexml = self.__get_request__(self._device_cap.TimeLink.href)
        return timexml

    def der_program_list(self,
                         edev_index: Optional[int] = 0,
                         fsa_index: Optional[int] = 0) -> m.DERProgramList:
        fsa = self.function_set_assignment(edev_index, fsa_index)
        derp_list = self.__get_request__(fsa.DERProgramListLink.href)
        return derp_list

    def der_program(self,
                    edev_index: Optional[int] = 0,
                    fsa_index: Optional[int] = 0,
                    derp_index: Optional[int] = 0) -> m.DERProgram:
        derp_list = self.der_program_list(edev_index, fsa_index)
        return derp_list.DERProgram[derp_index]

    def mirror_usage_point_list(self) -> m.MirrorUsagePointList:
        self._mup = self.__get_request__(self._device_cap.MirrorUsagePointListLink.href)
        return self._mup

    def usage_point_list(self) -> m.UsagePointList:
        self._upt = self.__get_request__(self._device_cap.UsagePointListLink.href)
        return self._upt

    def registration(self, end_device: m.EndDevice) -> m.Registration:
        reg = self.__get_request__(end_device.RegistrationLink.href)
        return reg

    def timelink(self):
        if self._device_cap is None:
            raise ValueError("Request device capability first")
        return self.__get_request__(url=self._device_cap.TimeLink.href)

    def disconnect(self):
        self._disconnect = True
        if self._dcap_timer:
            self._dcap_timer.cancel()
        IEEE2030_5_Client.clients.remove(self)

    def request(self, endpoint: str, body: dict = None, method: str = "GET", headers: dict = None):

        if method.upper() == 'GET':
            return self.__get_request__(endpoint, body, headers=headers)

        if method.upper() == 'POST':
            print("Doing post")
            return self.__post__(endpoint, body, headers=headers)

    def create_mirror_usage_point(self, mirror_usage_point: m.MirrorUsagePoint, point_num: int) -> Tuple[int, str]:
        data = utils.dataclass_to_xml(mirror_usage_point)
        #headers = {'Content-Type': 'text/xml', 'point_num': f"{point_num}", '333': '444'}  # 헤더는 helpdesk에서 날림
        headers = {'Content-Type': 'text/xml', '12345': f"{point_num}", '333': '444'}  # 헤더는 helpdesk에서 날림, 12345는 필터 안됨
        resp = self.__post__(self._device_cap.MirrorUsagePointListLink.href, data=data, headers=headers)
        return resp.status, resp.headers['Location']

    def create_mirror_meter_reading(self, mirror_usage_point_href: str,
                                    mirror_meter_reading: m.MirrorMeterReading) -> Tuple[int, str]:
        data = utils.dataclass_to_xml(mirror_meter_reading)
        resp = self.__post__(mirror_usage_point_href, data=data)
        return resp.status, resp.headers['Location']

    def post(self, url: str, data: Any, headers: Optional[Dict[str, str]] = None):
        response = self.__post__(url, data, headers=headers)

    def __post__(self, url: str, data=None, headers: Optional[Dict[str, str]] = None):
        if not headers:
            headers = {'Content-Type': 'text/xml'}

        self.http_conn.request(method="POST", headers=headers, url=url, body=data)
        response = self._http_conn.getresponse()
        # response_data = response.read().decode("utf-8")

        return response

    def __get_request__(self, url: str, body=None, headers: dict = None):
        if headers is None:
            headers = {"Connection": "keep-alive", "keep-alive": "timeout=30, max=1000"}

        if self._debug:
            print(f"----> GET REQUEST")
            print(f"url: {url} body: {body}")
        self.http_conn.request(method="GET", url=url, body=body, headers=headers)
        response = self._http_conn.getresponse()
        response_data = response.read().decode("utf-8")
        print(response.headers)

        response_obj = None
        try:
            response_obj = utils.xml_to_dataclass(response_data)
            resp_xml = xml.dom.minidom.parseString(response_data)
            if resp_xml and self._debug:
                print(f"<---- GET RESPONSE")
                print(f"{response_data}")    # toprettyxml()}")

        except xsdata.exceptions.ParserError as ex:
            if self._debug:
                print(f"<---- GET RESPONSE")
                print(f"{response_data}")
            response_obj = response_data

        return response_obj

    def __close__(self):
        self._http_conn.close()
        self._ssl_context = None
        self._http_conn = None

    def put(self, url: str, data: Any, headers: Optional[Dict[str, str]] = None):
        response = self.__put__(url, data, headers=headers)

    def __put__(self, url: str, data: Any, headers: Optional[Dict[str, str]] = None):
        if not headers:
            headers = {'Content-Type': 'text/xml'}

        if self._debug:
            _log_req_resp.debug(f"----> PUT REQUEST\nurl: {url}\nbody: {data}")

        try:
            self.http_conn.request(method="PUT", headers=headers, url=url, body=data)
        except http.client.CannotSendRequest as ex:
            self.http_conn.close()
            _log.debug("Reconnecting to server")
            self.http_conn.request(method="PUT", headers=headers, url=url, body=data)

        response = self._http_conn.getresponse()
        return response

    def __post__(self, url: str, data=None, headers: Optional[Dict[str, str]] = None):
        if not headers:
            headers = {'Content-Type': 'text/xml'}

        if self._debug:
            _log_req_resp.debug(f"----> POST REQUEST\nurl: {url}\nbody: {data}")

        self.http_conn.request(method="POST", headers=headers, url=url, body=data)
        response = self._http_conn.getresponse()
        response_data = response.read().decode("utf-8")
        # response_data = response.read().decode("utf-8")
        if response_data and self._debug:
            _log_req_resp.debug(f"<---- POST RESPONSE\n{response_data}")

        return response


# noinspection PyTypeChecker
def __release_clients__():
    for x in IEEE2030_5_Client.clients:
        x.__close__()
    IEEE2030_5_Client.clients = None


atexit.register(__release_clients__)

#
# ssl_context = ssl.create_default_context(cafile=str(SERVER_CA_CERT))
#
#
# con = HTTPSConnection("me.com", 8000,
#                       key_file=str(KEY_FILE),
#                       cert_file=str(CERT_FILE),
#                       context=ssl_context)
# con.request("GET", "/dcap")
# print(con.getresponse().read())
# con.close()

DEV_NUM = 4     # 1, 2, 3, 4, 5
HOST_IP = "3.138.199.28" #"34.235.134.18"  #server
# HOST_IP = "127.0.0.1"
# HOST_IP = "10.115.34.61"  #local

def Run_Measuring (gMsr):
    if DEV_NUM == 1:
        SERVER_CA_CERT = Path("./all_certs.pem").expanduser().resolve()
        KEY_FILE = Path("tls/private/dev1.pem").expanduser().resolve()
        CERT_FILE = Path("tls/certs/dev1.crt").expanduser().resolve()
    elif DEV_NUM == 2:
        SERVER_CA_CERT = Path("./all_certs.pem").expanduser().resolve()
        KEY_FILE = Path("tls/private/dev2.pem").expanduser().resolve()
        CERT_FILE = Path("tls/certs/dev2.crt").expanduser().resolve()
    elif DEV_NUM == 3:
        SERVER_CA_CERT = Path("./all_certs.pem").expanduser().resolve()
        KEY_FILE = Path("tls/private/dev3.pem").expanduser().resolve()
        CERT_FILE = Path("tls/certs/dev3.crt").expanduser().resolve()
    elif DEV_NUM == 4:
        SERVER_CA_CERT = Path("./all_certs.pem").expanduser().resolve()
        KEY_FILE = Path("tls/private/dev4.pem").expanduser().resolve()
        CERT_FILE = Path("tls/certs/dev4.crt").expanduser().resolve()
    elif DEV_NUM == 5:
        SERVER_CA_CERT = Path("./all_certs.pem").expanduser().resolve()
        KEY_FILE = Path("tls/private/dev5.pem").expanduser().resolve()
        CERT_FILE = Path("tls/certs/dev5.crt").expanduser().resolve()
    else:
        raise ("Wrong Device !!!!!!!!")

    headers = {'Connection': 'Keep-Alive', 'Keep-Alive': "max=1000,timeout=30"}

    h = IEEE2030_5_Client(cafile=SERVER_CA_CERT,
                          server_hostname=HOST_IP,#"127.0.0.1",
                          server_ssl_port=7443,
                          keyfile=KEY_FILE,
                          certfile=CERT_FILE,
                          debug=True)
    # h2 = IEEE2030_5_Client(cafile=SERVER_CA_CERT, server_hostname="me.com", ssl_port=8000,
    #                        keyfile=KEY_FILE, certfile=KEY_FILE)
    dcap = h.device_capability()
    end_devices = h.end_devices()

    if not end_devices.all > 0:
        print("registering end device.")
        ed_href = h.register_end_device()
    my_ed = h.end_devices().EndDevice[0]

    print(dcap.MirrorUsagePointListLink)
    print(h.request(dcap.MirrorUsagePointListLink.href))

    '''
    0: uuid
    1: description
    2: url
    3: accumulationBehaviour
    4: commodity
    5: dataQualifier
    6: flowDirection
    7: powerOfTenMultiplier
    8: uom
    '''
    ReadingInfos = [
        [0, 'PV1 Mode', '',        0, 0, 0, 0,     0, 0],
        [0, 'PV1 Vol.', '',        0, 0, 0, 0,     0, UomType.Voltage],
        [0, 'PV1 Cur.', '',        0, 0, 0, 0,     0, UomType.Amperes],
        [0, 'PV2 Mode', '',        0, 0, 0, 0,     0, 0],
        [0, 'PV2 Vol.', '',        0, 0, 0, 0,     0, UomType.Voltage],
        [0, 'PV2 Cur.', '',        0, 0, 0, 0,     0, UomType.Amperes],
        [0, 'PV3 Mode', '',        0, 0, 0, 0,     0, 0],
        [0, 'PV3 Vol.', '',        0, 0, 0, 0,     0, UomType.Voltage],
        [0, 'PV3 Cur.', '',        0, 0, 0, 0,     0, UomType.Amperes],
        [0, 'PV4 Mode', '',        0, 0, 0, 0,     0, 0],
        [0, 'PV4 Vol.', '',        0, 0, 0, 0,     0, UomType.Voltage],
        [0, 'PV4 Cur.', '',        0, 0, 0, 0,     0, UomType.Amperes],
        [0, 'Link Vol.', '',       0, 0, 0, 0,     0, UomType.Voltage],
        [0, 'PV1 Temp.', '',       0, 0, 0, 0,     0, UomType.Degrees_celsius],
        [0, 'PV2 Temp.', '',       0, 0, 0, 0,     0, UomType.Degrees_celsius],
        [0, 'Inv Temp.', '',       0, 0, 0, 0,     0, UomType.Degrees_celsius],
        [0, 'Inv Mode', '',        0, 0, 0, 0,     0, 0],
        [0, 'Grid Vol.', '',       0, 0, 0, 0,     0, UomType.Voltage],
        [0, 'Grid Cur.', '',       0, 0, 0, 0,     0, UomType.Amperes],
        [0, 'Grid Freq.', '',      0, 0, 0, 0,     0, UomType.Hz],
        [0, 'Real Power', '',      0, 0, 0, 0,     0, UomType.W],
        [0, 'Reactive Power', '',  0, 0, 0, 0,     0, UomType.VAr],
        [0, 'Apparent Power', '',  0, 0, 0, 0,     0, UomType.VA],
        [0, 'Power Factor', '',    0, 0, 0, 0,     0, 0]
    ]
    mups = h.mirror_usage_point_list()#(url=dcap.MirrorUsagePointListLink.href)
    if not mups.results or f"/mup_{DEV_NUM}" not in [mup.href for mup in mups.MirrorUsagePoint]:
        mup_uuid = h.new_uuid().encode('utf-8')
        mirror_meter_readings = list()
        for rd in ReadingInfos:
            mirror_meter_readings.append(m.MirrorMeterReading(
                mRID=h.new_uuid().encode('utf-8'),
                description=rd[1],
                Reading=m.Reading(value=0),
                ReadingType=m.ReadingType(
                    accumulationBehaviour=rd[3],
                    commodity=rd[4],
                    dataQualifier=rd[5],
                    flowDirection=rd[6],
                    powerOfTenMultiplier=rd[7],
                    uom=rd[8]
                )
            ))
        mup = m.MirrorUsagePoint(
            mRID=mup_uuid,
            description="Inverter",
            roleFlags=bytes(13),
            serviceCategoryKind=1,
            status=1,
            deviceLFDI=my_ed.lFDI,
            MirrorMeterReading=mirror_meter_readings
        )
        status, location = h.create_mirror_usage_point(mup, DEV_NUM)
        resp = h.request(location)
        print(resp)
        mups = h.mirror_usage_point_list()
        print(mups)
    mirror_usage_point_href, mup = [(mup.href, mup) for mup in mups.MirrorUsagePoint if mup.href == f"/mup_{DEV_NUM}"][0]
    for i, mmr in enumerate(mup.MirrorMeterReading):
        ReadingInfos[i][0] = mmr.mRID
        ReadingInfos[i][2] = mmr.href
    #with open('mup_6110A8AA.xml', 'r') as in_file:
    #    data = in_file.read()
    #    resp = h.__post__(dcap.MirrorUsagePointListLink.href, data=data)
    #    print(resp)
    c = -1
    i_find = [r[1] for r in ReadingInfos]
    while True:
        #if msvcrt.kbhit() or GLOBAL.Measuring_Stop > 0:
        if GLOBAL.Measuring_Stop > 0:
            break
        time.sleep(0.1)
        c += 1
        if c % 100 != 0:        # 100 => 10 sec
            continue
        print("flag : ", GLOBAL.Measuring_Stop)
        new = [None]*len(ReadingInfos)
        try:
            new[i_find.index('PV1 Vol.')] = gMsr['pv1_vol']
            new[i_find.index('PV2 Vol.')] = gMsr['pv2_vol']
            new[i_find.index('PV3 Vol.')] = gMsr['pv3_vol']
            new[i_find.index('PV4 Vol.')] = gMsr['pv4_vol']
            new[i_find.index('PV1 Cur.')] = gMsr['pv1_cur']
            new[i_find.index('PV2 Cur.')] = gMsr['pv2_cur']
            new[i_find.index('PV3 Cur.')] = gMsr['pv3_cur']
            new[i_find.index('PV4 Cur.')] = gMsr['pv4_cur']
            new[i_find.index('PV1 Mode')] = gMsr['pv1_mode']
            new[i_find.index('PV2 Mode')] = gMsr['pv2_mode']
            new[i_find.index('PV3 Mode')] = gMsr['pv3_mode']
            new[i_find.index('PV4 Mode')] = gMsr['pv4_mode']
            new[i_find.index('Link Vol.')] = gMsr['link_vol']
            new[i_find.index('PV1 Temp.')] = gMsr['pv1_temp']
            new[i_find.index('PV2 Temp.')] = gMsr['pv2_temp']
            new[i_find.index('Inv Temp.')] = gMsr['inv_temp']
            new[i_find.index('Inv Mode')] = gMsr['inv_mode']
            new[i_find.index('Grid Vol.')] = gMsr['grid_vol']
            new[i_find.index('Grid Cur.')] = gMsr['grid_cur']
            new[i_find.index('Grid Freq.')] = gMsr['grid_freq']
            new[i_find.index('Real Power')] = gMsr['act_pow']
            new[i_find.index('Reactive Power')] = gMsr['react_pow']
            new[i_find.index('Apparent Power')] = gMsr['appr_pow']
            new[i_find.index('Power Factor')] = gMsr['pf']
            update_meter_readings = m.MirrorMeterReadingList()
            for i, rd in enumerate(ReadingInfos):
                update_meter_readings.MirrorMeterReading.append(m.MirrorMeterReading(
                                                mRID=rd[0],
                                                Reading=m.Reading(value=new[i]),
                                                )
                )
            data = utils.dataclass_to_xml(update_meter_readings)
            resp = h.__post__(mirror_usage_point_href, data=data) #rd[2]
            reading = h.request(rd[2].replace("mup", "upt") + '_r')
            print(c, " => ", reading)
            #resp.status, resp.headers['Location']
        except:
            print ("Client Loop Error!")



if __name__ == '__main__':
    Run_Measuring ()
    #my_fsa = h.function_set_assignment()
    #my_program = h.der_program()

    # ed = h.end_devices()[0]
    # resp = h.request("/dcap", headers=headers)
    # print(resp)
    # resp = h.request("/dcap", headers=headers)
    # print(resp)
    #dcap = h.device_capability()
    # get device list
    #dev_list = h.request(dcap.EndDeviceListLink.href).EndDevice

    #ed = h.request(dev_list[0].href)
    #print(ed)
    #
    # print(dcap.mirror_usage_point_list_link)
    # # print(h.request(dcap.mirror_usage_point_list_link.href))
    # print(h.request("/dcap", method="post"))

    # tl = h.timelink()
    #print(IEEE2030_5_Client.clients)
