from handlers import index
from inspect import signature

sig = signature(index).parameters.keys()

print(sig)