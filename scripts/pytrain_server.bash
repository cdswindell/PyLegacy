#! /bin/bash
#
# change the following lines to define the path to where you installed PyTrain
# as well as the IP Address of your Legacy Base 3
PYTRAIN_HOME=/home/davids/dev/PyLegacyEnv/PyLegacy
LIONEL_BASE_3=192.168.1.124

# if a startup script is specified, use it if found
if [ -n "$BUTTONS_FILE" ]; then
  if [ -f $BUTTONS_FILE ]; then
    :
  elif [ -f $PYTRAIN_HOME/$BUTTONS_FILE ]; then
    BUTTONS_FILE=$PYTRAIN_HOME/$BUTTONS_FILE
  elif [ -f $PYTRAIN_HOME$BUTTONS_FILE ]; then
    BUTTONS_FILE=$PYTRAIN_HOME$BUTTONS_FILE
  else
    echo "Can not find button definitions file: $BUTTONS_FILE, continuing..."
    BUTTONS_FILE=
    START=
  fi

  if [ -n "$BUTTONS_FILE" ]; then
    echo "Using button definitions in: $BUTTONS_FILE"
    START=-buttons
  fi
fi

# change direction to PYTRAIN_HOME
cd $PYTRAIN_HOME

# activate the virtual environment
source ../bin/activate; export PYTHONPATH=.

# run the program
cli/pytrain.py -base $LIONEL_BASE_3 -ser2 -headless $START $BUTTONS_FILE

