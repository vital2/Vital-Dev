#!/bin/bash


### Print total arguments and their values

# echo "Total Arguments:" $#
# echo "All Arguments values:" $@

### Command arguments can be accessed as

# echo "First->"  $1
# echo "Second->" $2

# You can also access all arguments in an array and use them in a script.

args=("$@")
# echo "First->"  ${args[0]}
# echo "Second->" ${args[1]}

#/home/vital/.virtualenvs/vital/bin/python2.7 /home/vital/vital2.0/source/virtual
#_lab/vital_site/manage.py $@

# Activate the virtual environment
source /home/vital/vital2.0/source/prod-code/myenv/bin/activate

# Change to the directory where your Django project is located
cd /home/vital/vital2.0/source/prod-code/vital_site

# Run the Django development server
python2.7 manage.py $@
