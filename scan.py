# -*- coding: utf-8 -*-

import ipaddress
from typing import Any, Dict
import os,sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

import requests

_API_URL = "http://ip-api.com/json/{ip}"
_FIELDS = (
    "status,message,continent,continentCode,country,countryCode,"
    "region,regionName,city,district,zip,lat,lon,timezone,offset,"
    "currency,isp,org,as,asname,reverse,mobile,proxy,hosting,query"
)


def info(ip: str, lang: str = "zh-CN", timeout: int = 10) -> Dict[str, Any]:
    try:
        ip_obj = ipaddress.ip_address(ip)
    except ValueError as e:
        return False

    if ip_obj.version != 4:
        return False

    if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved:
        return False

    try:
        resp = requests.get(
            _API_URL.format(ip=ip),
            params={"lang": lang, "fields": _FIELDS},
            timeout=timeout,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        return False

    data = resp.json()
    if data.get("status") != "success":
        return False

    return {
        "ip":             data.get("query"),
        "version":        4,
        "continent":      data.get("continent"),
        "continent_code": data.get("continentCode"),
        "country":        data.get("country"),
        "country_code":   data.get("countryCode"),
        "region":         data.get("regionName"),
        "region_code":    data.get("region"),
        "city":           data.get("city"),
        "district":       data.get("district"),
        "zip":            data.get("zip"),
        "latitude":       data.get("lat"),
        "longitude":      data.get("lon"),
        "timezone":       data.get("timezone"),
        "utc_offset":     data.get("offset"),
        "currency":       data.get("currency"),
        "isp":            data.get("isp"),
        "org":            data.get("org"),
        "asn":            data.get("as"),
        "as_name":        data.get("asname"),
        "reverse_dns":    data.get("reverse"),
        "is_mobile":      data.get("mobile"),
        "is_proxy":       data.get("proxy"),
        "is_hosting":     data.get("hosting"),
        "raw":            data,
    }
