#!/bin/bash

exec python3 coke_diffusion/read_service.py &
exec python3 coke_diffusion/job_service.py &
exec python3 coke_diffusion/reply_service.py