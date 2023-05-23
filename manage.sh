#!/bin/bash

# Activate the virtual environment
source /home/vital/vital2.0/source/prod-code/myenv/bin/activate

# Change to the directory where your Django project is located
cd /home/vital/vital2.0/source/prod-code/vital_site

# Run the Django development server
python2.7 manage.py runserver 128.238.77.20:8799

