import math
import copy
import logging

from geographiclib.geodesic import Geodesic
geod = Geodesic.WGS84

from datetime import datetime

class ParsingError(Exception):
    pass

class ElementNotFoundError(ParsingError):
    def __init__(self, *args):
        logging.error(f"element {args[0]} not found in DB!")

class ElementAmbiguousError(ParsingError):
    def __init__(self, *args):
        logging.error(f"element {args[0]} is ambiguous!")

class NotOnAirwayError(ParsingError):
    def __init__(self, *args):
        logging.error(f"fix {args[0]} not found on airway {args[1]}!")

class IllegalCharacterError(ParsingError):
    def __init__(self, *args):
        logging.error(f"{args[0]} contains non alphanumeric characters")

class UnnamedFormatError(ParsingError):
    def __init__(self, *args):
        logging.error(f"Unnamed WPT {args[0]} has wrong format")

class UnnamedOutOfBounds(ParsingError):
    def __init__(self, *args):
        logging.error(f"Unnamed WPT {args[0]} coordinates out of boundaries")

class InitError(Exception):
    pass

class WrongAIRACcycleError(InitError):
    def __init__(self, *args):
        logging.error(f"{args[0]} has inconsistent AIRAC cycle")

class AIRACcycle:
    def __init__(self, _str):
        assert("AIRAC" in _str[1:6])
        self.cycle = int(_str[15:19])
        self.date_begin = datetime.strptime(_str[21:32], "%d/%b/%Y")
        self.date_end   = datetime.strptime(_str[35:46], "%d/%b/%Y")

        #self.date_str   = _str[21:46]
        self.date_str   = (self.date_begin.strftime("%d%b%y") + \
            " - " + self.date_end.strftime("%d%b%y")).upper()

    def __eq__(self, _other):
        return self.cycle == _other.cycle

class WayPoint:
    """docstring for ClassName"""
    def __init__(self, _name, _lat, _lon):
        self.name = _name        
        self.lat = float(_lat)
        self.lon = float(_lon)
        self.type = "WPT"
        self.descr = ""

    def distTo(self, _wpt2):
        g = geod.Inverse(self.lat, self.lon, _wpt2.lat, _wpt2.lon,)

        return g['s12']

    def distTrackTo(self, _wpt2):
        g = geod.Inverse(self.lat, self.lon, _wpt2.lat, _wpt2.lon,)


        az1 = g['azi1']
        az2 = g['azi2']
        if az1 < 0.: az1 += 360.
        if az2 < 0.: az2 += 360.
        return (g['s12'], (az1+az2) /2.)

    def distAzimuthsTo(self, _wpt2):
        g = geod.Inverse(self.lat, self.lon, _wpt2.lat, _wpt2.lon,)

        az1 = g['azi1']
        az2 = g['azi2']
        if az1 < 0.: az1 += 360.
        if az2 < 0.: az2 += 360.
        return (g['s12'], az1, az2)

    def getStr(self):
        return self.name + "     {0:10.6f}  {1:11.6f} ".format(self.lat, self.lon)

class NavAid(WayPoint):
    """docstring for ClassName"""
    def __init__(self, _name, _lat, _lon, _type, _descr):
        super(NavAid, self).__init__(_name, _lat, _lon)
        self.descr = _descr
        self.type = _type

class Airport(WayPoint):
    """docstring for ClassName"""
    def __init__(self, _name, _lat, _lon, _descr):
        super(Airport, self).__init__(_name, _lat, _lon)
        self.type = "ARP"
        self.descr = _descr

class Runway(WayPoint):
    """docstring for ClassName"""
    def __init__(self, _name, _lat, _lon, _descr):
        super(Runway, self).__init__(_name, _lat, _lon)
        self.type = "RWY"
        self.descr = _descr

class UnnamedWaypoint(WayPoint):
    """docstring for ClassName"""
    def __init__(self, _name):
        fixlen = len(_name)
        lat = 0.; latsgn = 1.
        lon = 0.; lonsgn = 1.

        # Honeywell format N1234.5/E16759.9, 15 char + /
        #                  0123456789_12345
        if fixlen == 16:
            if not (_name[0] in ("N","S") 
                and _name[8] in ("E", "W") 
                and _name[7] in "/" 
                and _name[5] in "."
                and _name[14] in "."
                and _name[1:5].isdigit()
                and _name[6].isdigit()
                and _name[9:14].isdigit()
                and _name[15].isdigit()
                ):
                raise(UnnamedFormatError(_name))

            latsgn = -1. if _name[0] == "S" else 1.
            lonsgn = -1. if _name[8] == "W" else 1.
            lat = latsgn*( float(_name[1:3]) + float(_name[3:7])/60.)
            lon = lonsgn*( float(_name[9:12]) + float(_name[12:16])/60.)

        # Thales format 1234N/01234E, 11 char + /
        #               0123456789_1234
        elif fixlen == 12:
            if not (_name[4] in ("N","S") 
                and _name[11] in ("E", "W") 
                and _name[5] in "/" 
                and _name[0:4].isdigit()
                and _name[6:11].isdigit()
                ):
                raise(UnnamedFormatError(_name))

            latsgn = -1. if _name[4] == "S" else 1.
            lonsgn = -1. if _name[11] == "W" else 1.
            lat = latsgn*( float(_name[0:2]) + float(_name[2:4])/60.)
            lon = lonsgn*( float(_name[6:9]) + float(_name[9:11])/60.)

        # OFP format 1234.5N01234.5E, 13 char
        #            0123456789_1234
        elif fixlen == 15:
            if not (_name[6] in ("N","S") 
                and _name[14] in ("E", "W") 
                and _name[4] in "."
                and _name[12] in "."
                and _name[0:4].isdigit()
                and _name[5].isdigit()
                and _name[7:12].isdigit()
                and _name[13].isdigit()
                ):
                raise(UnnamedFormatError(_name))

            latsgn = -1. if _name[6] == "S" else 1.
            lonsgn = -1. if _name[14] == "W" else 1.
            lat = latsgn*( float(_name[0:2]) + float(_name[2:6])/60.)
            lon = lonsgn*( float(_name[7:10]) + float(_name[10:14])/60.)

        # OFP format 1234N01234E, 11 char
        #            0123456789_
        elif fixlen == 11:
            if not (_name[4] in ("N","S") 
                and _name[10] in ("E", "W") 
                and _name[0:4].isdigit()
                and _name[5:10].isdigit()
                ):
                raise(UnnamedFormatError(_name))

            latsgn = -1. if _name[4] == "S" else 1.
            lonsgn = -1. if _name[10] == "W" else 1.
            lat = latsgn*( float(_name[0:2]) + float(_name[2:4])/60.)
            lon = lonsgn*( float(_name[5:8]) + float(_name[8:10])/60.)

        # unnamed format H0123, 5 char
        #                01234
        elif fixlen == 5:
            if not (_name[0] in ("H") 
                and _name[1:5].isdigit()
                ):
                raise(UnnamedFormatError(_name))

            latsgn = 1.
            lonsgn = -1.
            lat = latsgn*( float(_name[1:3]) + 0.5)
            lon = lonsgn*( float(_name[3:5]) )

        # unnamed format 87N060W, 7 char
        #                0123456
        elif fixlen == 7:
            if not (_name[2] in ("N","S") 
                and _name[6] in ("E", "W") 
                and _name[0:2].isdigit()
                and _name[3:6].isdigit()
                ):
                raise(UnnamedFormatError(_name))

            latsgn = -1. if _name[2] == "S" else 1.
            lonsgn = -1. if _name[6] == "W" else 1.
            lat = latsgn*( float(_name[0:2]) )
            lon = lonsgn*( float(_name[3:6]) )

        else:
            raise(UnnamedFormatError(_name))
            return None

        if (lat < -90.) or (lat > 90.) or (lon < -180.) or (lon > 180.):
            raise(UnnamedOutOfBounds(_name))

        super(UnnamedWaypoint, self).__init__(_name, lat, lon)
        self.type = "uWPT"

class Route:
    def __init__(self, _name):
        self.name = _name
        self._wpts = []
        self._wptnames = []

    def getWaypoints(self, _entry, _exit):
        try:
            _entry_index = self._wptnames.index(_entry)
        except ValueError:
            raise NotOnAirwayError(_entry, self.name)

        try:
            _exit_index  = self._wptnames.index(_exit)
        except ValueError:
            raise NotOnAirwayError(_exit, self.name)

        _step = 1

        if _entry_index > _exit_index:
            _step = -1

        _wpts = []
        for i in range(_entry_index, _exit_index, _step):
            _wpts.append(self._wpts[i])

        return _wpts

    def addWaypoint(self, _wpt):
        self._wpts.append(_wpt)
        self._wptnames.append(_wpt.name)
        pass

class NavDB:
    def __init__(self, datadir="navdata"):
        self.airac= None
        self._awys = {}
        self._wpts = {}
        self._load(datadir=datadir)

    def reload(self, datadir="navdata"):
        self.airac= None
        self._awys = {}
        self._wpts = {}
        self._load(datadir=datadir)

    def _load(self, datadir="navdata"):
        wpts = {}
        nold = 0
        logging.info("loading NavAids ...")
        with open(datadir + "/wpNavAID.txt", "r") as f:
            for l in f:
                # ignore comments
                if l[0] == ";":
                    if "AIRAC" in l[1:6]:
                        if not self.airac:
                            self.airac = AIRACcycle(l)
                        else:
                            if not AIRACcycle(l) == self.airac:
                                raise WrongAIRACcycleError("wpNavAID.txt")
                    continue
                else:
                    name = l[24:28].rstrip()

                    wpts.setdefault(name,[]).append( 
                        NavAid(name, float(l[33:43]), float(l[43:54]), 
                            l[29:33].rstrip(), l[:24].rstrip() ) )
                    nold += 1
        logging.info("    --> %i NavAids" % nold)
        self._nonavaids = nold

        nold = 0
        logging.info("loading fixes ...")
        with open(datadir + "/wpNavFIX.txt", "r") as f:
            for l in f:
                if l[0] == ";":
                    if "AIRAC" in l[1:6]:
                        if not self.airac:
                            self.airac = AIRACcycle(l)
                        else:
                            if not AIRACcycle(l) == self.airac:
                                raise WrongAIRACcycleError("wpNavFIX.txt")
                    continue
                else:
                    name = l[0:5].rstrip()

                    wpts.setdefault(name,[]).append( 
                    WayPoint(name, float(l[29:39]), float(l[39:])) )
                    nold += 1

        logging.info("    --> %i fixes" % nold)
        self._nofixes = nold

        nold = 0
        logging.info("loading Runways ...")
        with open(datadir + "/wpNavAPT.txt", "r") as f:
            for l in f:
                if l[0] == ";":
                    if "AIRAC" in l[1:6]:
                        if not self.airac:
                            self.airac = AIRACcycle(l)
                        else:
                            if not AIRACcycle(l) == self.airac:
                                raise WrongAIRACcycleError("wpNavFIX.txt")
                    continue
                else:
                    name = (l[24:28] + "R" + l[28:31]).strip()
                    wpts.setdefault(name,[]).append( 
                        Runway(name, 
                            float(l[39:49]), 
                            float(l[49:60]), 
                            (l[0:24]).strip() )
                        )
                    nold += 1
        logging.info("    --> %i runways" % nold)
        self._norwys = nold

        nold = 0
        logging.info("loading Airports ...")
        with open(datadir + "/airports.dat", "r") as f:
            for l in f:
                if l[0] == ";":
                    if "AIRAC" in l[1:6]:
                        if not self.airac:
                            self.airac = AIRACcycle(l)
                        else:
                            if not AIRACcycle(l) == self.airac:
                                raise WrongAIRACcycleError("airports.dat")
                    continue
                else:
                    name = l[0:4]
                    wpts.setdefault(name,[]).append( 
                        Airport(name, float(l[4:14]), float(l[14:]), "") )
                    nold += 1
        logging.info("    --> %i airports" % nold)
        self._noarpts = nold
        self._wpts = wpts

        nold = 0
        awys = {}
        logging.info("loading Airways ...")
        with open(datadir + "/wpNavRTE.txt", "r") as f:
            cawy = None
            for l in f:
                # ignore comments
                if l[0] == ";":
                    if "AIRAC" in l[1:6]:
                        if not self.airac:
                            self.airac = AIRACcycle(l)
                        else:
                            if not AIRACcycle(l) == self.airac:
                                raise WrongAIRACcycleError("wpNavRTE.txt")
                    continue

                else:
                    # valid wpt line
                    [name, nr, wptname, lats, lons] = l.split()

                    # create a current route if necessary
                    if not cawy:
                        cawy = Route(name)

                    # wpt line part of current route
                    if cawy.name == name:
                        cawy.addWaypoint(WayPoint(wptname, float(lats), float(lons)))

                    # new airway. flush current route and create new one
                    else:
                        awys[cawy.name] = cawy
                        nold += 1
                        cawy = Route(name)
                        cawy.addWaypoint(WayPoint(wptname, float(lats), float(lons)))

            # flush last awy
            else:
                nold += 1
                awys[cawy.name] = cawy
        
        logging.info("    --> %i airways" % nold)
        self._noawys = nold
        self._awys = awys

    def getClosest(self, _name, _close_wpt):
        try:
            wpt_pot = self._wpts[_name]
        except:
            raise(ElementNotFoundError(_name))

        if len(wpt_pot) == 1:
            return wpt_pot[0]

        if not _close_wpt:
            raise(ElementAmbiguousError(_name))

        wpt_dst = []
        for w in wpt_pot:
            d = w.distTo(_close_wpt)
            wpt_dst.append( d )

        return wpt_pot[ wpt_dst.index(min(wpt_dst)) ]

    def expandFPL(self, _fpl):
        wpts = []

        fpl_arr = _fpl.split()
        fpl_sz  = len(fpl_arr)

        last_wpt = None
        apts_found = 0

        for elem in fpl_arr:
            if not elem.replace('/','').replace('.','').isalnum() or elem.count("/") > 1:
                raise IllegalCharacterError(elem)

        for i in range(fpl_sz):
            elem = fpl_arr[i]
            elem_type = self.getFPLelemtype(elem)
            logging.debug("element %s    is    %s " % (elem, elem_type) )

            if elem_type == "awy" and (i-1 >= 0) and (i+1 < fpl_sz):
                awy_start = fpl_arr[i-1]
                awy_end   = fpl_arr[i+1]
                awy_name  = fpl_arr[i]

                try:
                    awy = self._awys[awy_name]
                except:
                    raise(ElementNotFoundError(awy_name))

                awy_wpts = awy.getWaypoints(awy_start, awy_end)

                # only append waypoints between start and end
                for w in awy_wpts[1:]:
                    wpts.append(w)

                last_wpt = awy_wpts[-1]

            elif elem_type == "prc" and (i-1 >= 0) and (i+1 < fpl_sz):
                pelem = self.getFPLelemtype(fpl_arr[i-1])
                nelem = self.getFPLelemtype(fpl_arr[i+1])

                # it's a SID
                wpt = None
                if nelem == "fix" and (pelem in ("rwy", "arp")):
                    wpt = self.getClosest(fpl_arr[i+1], self._wpts[ (fpl_arr[i-1])[0:4]][0])

                # it's a STAR
                if pelem == "fix" and (nelem in ("rwy", "arp")):
                    wpt = self.getClosest(fpl_arr[i-1], self._wpts[ (fpl_arr[i+1])[0:4]][0])
                    if wpt == last_wpt:
                        wpt = None

                if wpt:
                    wpts.append(wpt)
                    last_wpt = wpt

            elif elem_type == "apt" or elem_type == "rwy":
                if apts_found < 2:
                    try:
                        arp = self._wpts[elem][0]
                    except:
                        raise(ElementNotFoundError(elem))
                    wpts.append(arp)
                    apts_found += 1
                    last_wpt = arp

            elif elem_type == "ufx":
                wpt = UnnamedWaypoint(elem)

                if wpt.distTo(last_wpt) < 0.1:
                    wpt = None

                if wpt:
                    wpts.append(wpt)
                    last_wpt = wpt

            elif elem_type == "fix":
                wpt = self.getClosest(elem, last_wpt)

                if wpt == last_wpt:
                    wpt = None

                if wpt:
                    wpts.append(wpt)
                    last_wpt = wpt

        # return list of waypoint copies, so that modification of returned waypoints 
        # does not alter the elements in the database
        wpts_ret = []
        for w in wpts:
            wpts_ret.append(copy.copy(w))

        return wpts_ret

    def getFPLelemtype(self, _elem):
        no_aph = sum(c.isalpha() for c in _elem)
        no_dig = sum(c.isdigit() for c in _elem)
        no_dir = sum(_elem.count(c) for c in ("N","S","W","E") )
        no_tot = len(_elem)

        # direct-to keyword
        if _elem == "DCT":
            return "dct"

        # unnamed WPT
        elif (no_dir == 2 and no_tot in (7, 11, 12, 15, 16) and no_dig >= 5):
            return "ufx"

        # unnamed half-degree WPT Hnnww
        elif (no_tot == 5 and _elem[0] == "H" and no_dig == 4):
            return "ufx"

        # NAT track designator
        elif no_tot == 4 and "NAT" in _elem[0:3]:
            if _elem[3].isalpha():
                return "nat"

        # ICAO airport code
        elif (no_tot == 4 and no_dig == 0):
            return "apt"

        # runway designator
        elif no_tot in (7,8) and _elem[4] == "R" and _elem[5:7].isdigit():
            return "rwy"

        # unnamed waypoint from database
        elif (no_aph == 1 and no_dig >= 4):
            return "fix"

        # RNAV WPT or NavAid, less than 6 letters
        elif _elem.isalpha() and no_tot < 6:
            return "fix"

        # is the name in the Airways list?
        elif _elem in self._awys.keys():
            return "awy"

        # is the name in the Waypoint list?
        elif _elem in self._wpts.keys():
            return "fix"

        # anything else must be a procedure
        else:
            return "prc"


