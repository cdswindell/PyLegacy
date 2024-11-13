#! /bin/bash
#
# change the following lines to define the path to where you installed PyTrain
# as well as the IP Address of your Legacy Base 3
PYTRAIN_HOME=/home/davids/dev/PyLegacyEnv/PyLegacy
PYTRAIN_SERVER=192.168.3.150
STARTUP_SCRIPT=examples/buttons.py

# if a startup script is specified, use it if found
if [ -n "$STARTUP_SCRIPT" ]; then
  if [ -f $STARTUP_SCRIPT ];
    :
  elif [ -f $PYTRAIN_HOME/$STARTUP_SCRIPT ]; then
    STARTUP_SCRIPT=$PYTRAIN_HOME/$STARTUP_SCRIPT
  elif [ -f $PYTRAIN_HOME$STARTUP_SCRIPT ]; then
    STARTUP_SCRIPT=$PYTRAIN_HOME$STARTUP_SCRIPT
  else
    echo "Can not locate start-up script: $STARTUP_SCRIPT, continuing..."
    STARTUP_SCRIPT=
    START=
  fi

  if [ -n "$STARTUP_SCRIPT" ]; then
    echo "Using start-up script: $STARTUP_SCRIPT"
    START=-start
  fi
fi
# change direction to PYTRAIN_HOME
cd $PYTRAIN_HOME
# activate the virtual environment
source ../bin/activate; export PYTHONPATH=.
# run the program
src/cli/pytrain.py -server $PYTRAIN_SERVER $START $STARTUP_SCRIPT

