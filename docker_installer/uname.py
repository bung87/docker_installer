#-*- coding: utf-8 -*-
import platform,sys
uname =  platform.uname \
if sys.version_info < (3,3) \
else  (platform.system(), platform.node(), platform.release(), platform.version(), platform.machine(), platform.processor())
print( u"萌".join(uname).encode("utf8") )