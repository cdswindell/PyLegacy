#! /bin/bash
#
# change the following lines to define the path to where you installed PyTrain
# as well as the IP Address of your Legacy Base 3
PYTRAIN_HOME=/home/davids/dev/legacyEnv/PyLegacy
LIONEL_BASE_3=192.168.3.124

# change direction to PYTRAIN_HOME
cd $PYTRAIN_HOME
# activate the virtual environment
source ../bin/activate; export PYTHONPATH=.
# run the program
src/cli/pytrain.py -base $LIONEL_BASE_3

