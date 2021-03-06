import platform,re,sys
if sys.version_info < (3,3):
    (system, node, release, version, machine, processor) = platform.uname()
else:
    (system, node, release, version, machine, processor) = (platform.system(), platform.node(), platform.release(), platform.version(), platform.machine(), platform.processor())
os_market_name = release = ""
if version.find("Ubuntu") > 0:
    os_market_name = "Ubuntu"
    found = re.findall("\d+\.\d+\.\d+", version)
    if len(found):
        release = found[0]
elif system == "Linux":
    try:
        import lsb_release
        lsb = lsb_release.get_lsb_information();
        os_market_name = lsb.get("ID")
        release = lsb.get("RELEASE") # Ubuntu '16.04'
    except Exception as e:
        import platform
        lsb = platform.linux_distribution()
        os_market_name = lsb[0].split(" ")[0]
        release = lsb[1] # CentOS 7.3.1611
result = (os_market_name,release)
print(result)