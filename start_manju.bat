@echo off
chcp 65001 >nul
title 漫镜工场 ManJu Studio 一键启动
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0start_manju.ps1"
