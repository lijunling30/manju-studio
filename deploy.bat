@echo off
title ManJu Studio Deploy
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy.ps1" %*
pause
