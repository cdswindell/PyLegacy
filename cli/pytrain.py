#!/usr/bin/env python3
#
from src.pytraincli.pytrain import PyTrain, arg_parser

if __name__ == "__main__":
    PyTrain(arg_parser().parse_args())
