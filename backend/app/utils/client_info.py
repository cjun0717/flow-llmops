#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
客户端信息提取工具
从HTTP请求中提取客户端IP、浏览器、操作系统等信息
"""
from fastapi import Request


def get_client_info(request: Request) -> dict:
    """
    从请求中提取客户端信息
    
    Args:
        request: FastAPI Request对象
    
    Returns:
        dict: 包含以下字段:
            - login_ip: 客户端IP地址
            - user_agent: 完整的User-Agent字符串
            - browser_type: 浏览器类型
            - os_type: 操作系统类型
            - device_type: 设备类型 (desktop/mobile/tablet)
    """
    # 获取IP地址
    login_ip = request.headers.get("X-Forwarded-For", "")
    if login_ip:
        login_ip = login_ip.split(",")[0].strip()
    else:
        login_ip = request.client.host if request.client else "0.0.0.0"
    
    # 获取User-Agent
    user_agent = request.headers.get("User-Agent", "")
    
    # 解析浏览器和操作系统
    browser_type = None
    os_type = None
    device_type = "desktop"
    
    ua_lower = user_agent.lower()
    
    # 浏览器检测
    if "chrome" in ua_lower and "edg" not in ua_lower:
        browser_type = "Chrome"
    elif "firefox" in ua_lower:
        browser_type = "Firefox"
    elif "safari" in ua_lower and "chrome" not in ua_lower:
        browser_type = "Safari"
    elif "edg" in ua_lower:
        browser_type = "Edge"
    elif "msie" in ua_lower or "trident" in ua_lower:
        browser_type = "IE"
    
    # 操作系统检测
    if "windows" in ua_lower:
        os_type = "Windows"
    elif "mac os" in ua_lower or "macos" in ua_lower:
        os_type = "macOS"
    elif "linux" in ua_lower:
        os_type = "Linux"
    elif "android" in ua_lower:
        os_type = "Android"
        device_type = "mobile"
    elif "iphone" in ua_lower or "ipad" in ua_lower:
        os_type = "iOS"
        device_type = "mobile" if "iphone" in ua_lower else "tablet"
    
    return {
        "login_ip": login_ip,
        "user_agent": user_agent,
        "browser_type": browser_type,
        "os_type": os_type,
        "device_type": device_type,
    }


def get_client_ip(request: Request) -> str:
    """
    仅获取客户端IP地址
    
    Args:
        request: FastAPI Request对象
    
    Returns:
        str: 客户端IP地址
    """
    login_ip = request.headers.get("X-Forwarded-For", "")
    if login_ip:
        return login_ip.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"
