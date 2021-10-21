"""Create custom particle classes and kernels inside here"""
import math
from operator import attrgetter
import sys

import numpy as np
from parcels import JITParticle, Variable
from parcels import ParcelsRandom


ParcelsRandom.seed(42)


class ThreddsParticle(JITParticle):
    """
    Not actually Thredds specific, just a particle that tracks its own lifetime, spawntime,
    and when it goes out of bounds.
    """
    lifetime = Variable("lifetime", initial=0, dtype=np.float32)
    spawntime = Variable("spawntime", initial=attrgetter("time"), dtype=np.float32)
    # out of bounds
    oob = Variable("oob", initial=0, dtype=np.int32)


def AgeParticle(particle, fieldset, time):
    """Kernel to age particles."""
    particle.lifetime += particle.dt


def RandomWalk(particle, fieldset, time):
    """
    Adds random noise to particle movement (ripped from the plume tracker).

    I'm not entirely sure what's up with the units or something, but 5 cm/s error barely
    adds any randomness to the movement. Maybe something is wrong.
    """
    uerr = 5 / 100  # 5 cm/s uncertainty with radar
    th = 2 * math.pi * ParcelsRandom.random()  # randomize angle of error
    # convert from degrees to m
    u_conv = 1852 * 60 * math.cos(particle.lat * math.pi / 180)  # lon convert
    v_conv = 1852 * 60  # lat convert
    u_n = uerr * math.cos(th)
    v_n = uerr * math.sin(th)
    dx = u_n * particle.dt
    dy = v_n * particle.dt
    # undo conversion
    dx /= u_conv
    dy /= v_conv
    particle.lon += dx
    particle.lat += dy


def TestOOB(particle, fieldset, time):
    """
    Kernel to test if a particle has gone into a location without any ocean current data.
    """
    OOB_THRESH = 1e-14
    u, v = fieldset.UV[time, particle.depth, particle.lat, particle.lon]
    if math.fabs(u) < OOB_THRESH and math.fabs(v) < OOB_THRESH:
        particle.oob = 1
    else:
        particle.oob = 0


def DeleteOOB(particle, fieldset, time):
    """Deletes particles that go out of bounds"""
    OOB_THRESH = 1e-14
    u, v = fieldset.UV[time, particle.depth, particle.lat, particle.lon]
    if math.fabs(u) < OOB_THRESH and math.fabs(v) < OOB_THRESH:
        particle.delete()


def DeleteAfter3Days(particle, fieldset, time):
    """Deletes a particle after 3 days (should probably rename this for that)"""
    LIFETIME = 259200
    if particle.lifetime > LIFETIME:
        particle.delete()


def DeleteParticle(particle, fieldset, time):
    """Deletes a particle. Mainly for use with the recovery kernel."""
    particle.delete()


def DeleteParticleVerbose(particle, fieldset, time):
    print(f"Particle [{particle.id}] lost "
          f"({particle.time}, {particle.depth}, {particle.lat}, {particle.lon})", file=sys.stderr)
    particle.delete()


def WindModify3Percent(particle, fieldset, time):
    """please dont use this yet idk what im doing"""
    wu = fieldset.WU[time, particle.depth, particle.lat, particle.lon]
    wv = fieldset.WV[time, particle.depth, particle.lat, particle.lon]
    # convert from degrees/s to m/s
    u_conv = 1852 * 60 * math.cos(particle.lat * math.pi / 180)
    v_conv = 1852 * 60
    wu_conv = wu * 0.03 / u_conv
    wv_conv = wv * 0.03 / v_conv
    particle.lon += wu_conv * particle.dt
    particle.lat += wv_conv * particle.dt
