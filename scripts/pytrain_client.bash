#! /bin/bash
#
# change the following lines to define the path to where you installed PyTrain
# as well as the namer of the startup script to load, if any
PYTRAIN_HOME=/home/davids/dev/PyLegacyEnv/PyLegacy
BUTTONS_FILE=examples/buttons.py

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
    echo "Using start-up script: $BUTTONS_FILE"
    START=-buttons
  fi
fi

# change direction to PYTRAIN_HOME
cd $PYTRAIN_HOME

# activate the virtual environment
source ../bin/activate; export PYTHONPATH=.

# run the program
cli/pytrain.py -client -headless $START $BUTTONS_FILE
