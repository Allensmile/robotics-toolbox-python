#!/usr/bin/env python
"""
@author: Jesse Haviland
"""

import copy
import numpy as np
from spatialmath import SE3
import roboticstoolbox as rp
from roboticstoolbox.robot.Link import Link, _listen_dyn

_eps = np.finfo(np.float64).eps

# --------------------------------------------------------------#

try:  # pragma: no cover
    # print('Using SymPy')
    import sympy as sym

    def _issymbol(x):
        return isinstance(x, sym.Expr)
except ImportError:
    def _issymbol(x):  # pylint: disable=unused-argument
        return False

def _cos(theta):
    if _issymbol(theta):
        return sym.cos(theta)
    else:
        return np.cos(theta)


def _sin(theta):
    if _issymbol(theta):
        return sym.sin(theta)
    else:
        return np.sin(theta)

# --------------------------------------------------------------#


class DHLink(Link):
    """
    A link superclass for all robots defined using Denavit-Hartenberg notation.
    A Link object holds all information related to a robot joint and link such
    as kinematics parameters, rigid-body inertial parameters, motor and
    transmission parameters.

    :param theta: kinematic: joint angle
    :type theta: float
    :param d: kinematic - link offset
    :type d: float
    :param alpha: kinematic - link twist
    :type alpha: float
    :param a: kinematic - link length
    :type a: float
    :param sigma: kinematic - 0 if revolute, 1 if prismatic
    :type sigma: int
    :param mdh: kinematic - 0 if standard D&H, else 1
    :type mdh: int
    :param offset: kinematic - joint variable offset
    :type offset: float

    :param qlim: joint variable limits [min, max]
    :type qlim: ndarray(2,)
    :param flip: joint moves in opposite direction
    :type flip: bool

    :param m: dynamic - link mass
    :type m: float
    :param r: dynamic - position of COM with respect to link frame
    :type r:  ndarray(3,)
    :param I: dynamic - inertia of link with respect to COM
    :type I: ndarray
    :param Jm: dynamic - motor inertia
    :type Jm: float
    :param B: dynamic - motor viscous friction: B=B⁺=B⁻, [B⁺, B⁻]
    :type B: float, or ndarray(2,)
    :param Tc: dynamic - motor Coulomb friction [Tc⁺, Tc⁻]
    :type Tc: ndarray(2,)
    :param G: dynamic - gear ratio
    :type G: float

    :references:
        - Robotics, Vision & Control, P. Corke, Springer 2011, Chap 7.

    """

    def __init__(
            self,
            d=0.0,
            alpha=0.0,
            theta=0.0,
            a=0.0,
            sigma=0,
            mdh=False,
            **kwargs):

        # TODO
        #  probably should make DHLink(link) return a copy
        #  probably should enforce keyword arguments, easy to make an
        #    error with positional args
        super().__init__(**kwargs)

        # Kinematic parameters
        self.sigma = sigma
        self.theta = theta
        self.d = d
        self.alpha = alpha
        self.a = a
        self.mdh = mdh
        self.id = None


    def __add__(self, L):
        if isinstance(L, DHLink):
            return rp.DHRobot([self, L])

        elif isinstance(L, rp.DHRobot):
            nlinks = [self]

            # TODO - Should I do a deep copy here a physically copy the Links
            # and not just the references?
            # Copy Link references to new list
            for i in range(L.n):
                nlinks.append(L.links[i])

            return rp.DHRobot(
                nlinks,
                name=L.name,
                manufacturer=L.manufacturer,
                base=L.base,
                tool=L.tool,
                gravity=L.gravity)

        else:
            raise TypeError("Cannot add a Link with a non Link object")

    def __str__(self):

        if not self.sigma:
            s = "Revolute   theta=q{} +{: .2f},  d={: .2f},  a={: .2f},  " \
                "alpha={: .2f}".format(
                    self.id, self.offset, self.d, self.a, self.alpha)
        else:
            s = "Prismatic  theta={: .2f},  d=q{} +{: .2f},  a={: .2f},  " \
                "alpha={: .2f}".format(
                    self.theta, self.id, self.offset, self.a, self.alpha, )

        return s

    def __repr__(self):
        return str(self)


    @property
    def d(self):
        """
        Get/set link offset

        - ``link.d`` is the link offset
            :return: link offset
            :rtype: float
        - ``link.d = ...`` checks and sets the link offset

        """
        return self._d

    @property
    def alpha(self):
        """
        Get/set link twist

        - ``link.d`` is the link twist
            :return: link twist
            :rtype: float
        - ``link.d = ...`` checks and sets the link twist

        """
        return self._alpha

    @property
    def theta(self):
        """
        Get/set joint angle

        - ``link.theta`` is the joint angle
            :return: joint angle
            :rtype: float
        - ``link.theta = ...`` checks and sets the joint angle

        """
        return self._theta

    @property
    def a(self):
        """
        Get/set link length

        - ``link.a`` is the link length
            :return: link length
            :rtype: float
        - ``link.a = ...`` checks and sets the link length

        """
        return self._a

    @property
    def sigma(self):
        """
        Get/set joint type

        - ``link.sigma`` is the joint type
            :return: joint type
            :rtype: int
        - ``link.sigma = ...`` checks and sets the joint type

        The joint type is 0 for a revolute joint, and 1 for a prismatic joint.

        :seealso: :func:`isrevolute`, :func:`isprismatic`
        """
        return self._sigma

    @property
    def mdh(self):
        """
        Get/set kinematic convention

        - ``link.mdh`` is the kinematic convention
            :return: kinematic convention
            :rtype: bool
        - ``link.mdh = ...`` checks and sets the kinematic convention

        The kinematic convention is True for modified Denavit-Hartenberg
        notation (eg. Craig's textbook) and False for Denavit-Hartenberg
        notation (eg. Siciliano, Spong, Paul textbooks).
        """
        return self._mdh

    @d.setter
    @_listen_dyn
    def d(self, d_new):
        if self.sigma and d_new != 0.0:
            raise ValueError("f is not valid for prismatic joints")
        else:
            self._d = d_new

    @alpha.setter
    @_listen_dyn
    def alpha(self, alpha_new):
        self._alpha = alpha_new

    @theta.setter
    @_listen_dyn
    def theta(self, theta_new):
        if not self.sigma and theta_new != 0.0:
            raise ValueError("theta is not valid for revolute joints")
        else:
            self._theta = theta_new

    @a.setter
    @_listen_dyn
    def a(self, a_new):
        self._a = a_new

    @sigma.setter
    @_listen_dyn
    def sigma(self, sigma_new):
        self._sigma = sigma_new

    @mdh.setter
    @_listen_dyn
    def mdh(self, mdh_new):
        self._mdh = int(mdh_new)

    def A(self, q):
        r"""
        Link transform matrix

        :param q: Joint coordinate
        :type q: float
        :return T: SE(3) link homogeneous transformation
        :rtype T: SE3 instance

        ``A(q)`` is an ``SE3`` instance representing the SE(3) homogeneous
        transformation matrix corresponding to the link's joint variable ``q``
        which is either the Denavit-Hartenberg parameter :math:`\theta_j`
        (revolute) or :math:`d_j` (prismatic). 
        
        This is the relative pose of the current link frame with respect to the
        previous link frame.



        For details of the computation see the documentation for the subclasses,
        click on the right side of the class boxes below. 

        .. inheritance-diagram:: roboticstoolbox.RevoluteDH roboticstoolbox.PrismaticDH roboticstoolbox.RevoluteMDH roboticstoolbox.PrismaticMDH
            :top-classes: roboticstoolbox.robot.DHLink.DHLink
            :parts: 2

        .. note::

            - For a revolute joint the ``theta`` parameter of the link is 
              ignored, and ``q`` used instead.
            - For a prismatic joint the ``d`` parameter of the link is ignored,
              and ``q`` used instead.
            - The joint ``offset`` parameter is added to ``q`` before 
              computation of the transformation matrix.
            - The computation is different for standard and modified 
              Denavit-Hartenberg parameters.

        :seealso: :class:`RevoluteDH`, :class:`PrismaticDH`, :class:`RevoluteMDH`, :class:`PrismaticMDH`
        """

        sa = _sin(self.alpha)
        ca = _cos(self.alpha)

        if self.flip:
            q = -q + self.offset
        else:
            q = q + self.offset

        if self.sigma == 0:
            # revolute
            st = _sin(q)
            ct = _cos(q)
            d = self.d
        else:
            # prismatic
            st = _sin(self.theta)
            ct = _cos(self.theta)
            d = q

        if self.mdh == 0:
            # standard DH
            T = np.array([
                [ct, -st * ca, st * sa, self.a * ct],
                [st, ct * ca, -ct * sa, self.a * st],
                [0, sa, ca, d],
                [0, 0, 0, 1]
            ])
        else:
            # modified DH
            T = np.array([
                [ct, -st, 0, self.a],
                [st * ca, ct * ca, -sa, -sa * d],
                [st * sa, ct * sa, ca, ca * d],
                [0, 0, 0, 1]
            ])

        return SE3(T, check=False)

    def isrevolute(self):
        """
        Checks if the joint is of revolute type

        :return: Ture if is revolute
        :rtype: bool

        :seealso: :func:`sigma`
        """

        if not self.sigma:
            return True
        else:
            return False

    def isprismatic(self):
        """
        Checks if the joint is of prismatic type

        :return: Ture if is prismatic
        :rtype: bool

        :seealso: :func:`sigma`
        """

        if self.sigma:
            return True
        else:
            return False


# -------------------------------------------------------------------------- #
class RevoluteDH(DHLink):
    r"""
    Class for revolute links using standard DH convention

    :param d: kinematic - link offset
    :type d: float
    :param alpha: kinematic - link twist
    :type alpha: float
    :param a: kinematic - link length
    :type a: float
    :param offset: kinematic - joint variable offset
    :type offset: float

    :param qlim: joint variable limits [min, max]
    :type qlim: float ndarray(1,2)
    :param flip: joint moves in opposite direction
    :type flip: bool

    :param m: dynamic - link mass
    :type m: float
    :param r: dynamic - position of COM with respect to link frame
    :type r:  float ndarray(3)
    :param I: dynamic - inertia of link with respect to COM
    :type I: ndarray
    :param Jm: dynamic - motor inertia
    :type Jm: float
    :param B: dynamic - motor viscous friction: B=B⁺=B⁻, [B⁺, B⁻]
    :type B: float, or ndarray(2,)
    :param Tc: dynamic - motor Coulomb friction [Tc⁺, Tc⁻]
    :type Tc: ndarray(2,)
    :param G: dynamic - gear ratio
    :type G: float

    A subclass of the :class:`DHLink` class for a revolute joint that holds all
    information related to a robot link such as kinematics parameters,
    rigid-body inertial parameters, motor and transmission parameters.

    The link transform is

    :math:`\underbrace{\mathbf{T}_{rz}(q_i)}_{\mbox{variable}} \cdot \mathbf{T}_{tz}(d_i) \cdot \mathbf{T}_{tx}(a_i) \cdot \mathbf{T}_{rx}(\alpha_i)`

    where :math:`q_i` is the joint variable.

    :references:
        - Robotics, Vision & Control, P. Corke, Springer 2011, Chap 7.

    :seealso: :func:`PrismaticDH`, :func:`DHLink`, :func:`RevoluteMDH`
    """

    def __init__(
            self,
            d=0.0,
            a=0.0,
            alpha=0.0,
            offset=0.0,
            qlim=np.zeros(2),
            flip=False,
            **kwargs
            ):

        theta = 0.0
        sigma = 0
        mdh = False

        super().__init__(
            d=d, alpha=alpha, theta=theta, a=a, sigma=sigma, mdh=mdh,
            offset=offset, qlim=qlim, flip=flip, **kwargs)


class PrismaticDH(DHLink):
    r"""
    Class for prismatic link using standard DH convention

    :param theta: kinematic: joint angle
    :type theta: float
    :param d: kinematic - link offset
    :type d: float
    :param alpha: kinematic - link twist
    :type alpha: float
    :param a: kinematic - link length
    :type a: float
    :param offset: kinematic - joint variable offset
    :type offset: float

    :param qlim: joint variable limits [min, max]
    :type qlim: float ndarray(1,2)
    :param flip: joint moves in opposite direction
    :type flip: bool

    :param m: dynamic - link mass
    :type m: float
    :param r: dynamic - position of COM with respect to link frame
    :type r:  float ndarray(3)
    :param I: dynamic - inertia of link with respect to COM
    :type I: ndarray
    :param Jm: dynamic - motor inertia
    :type Jm: float
    :param B: dynamic - motor viscous friction: B=B⁺=B⁻, [B⁺, B⁻]
    :type B: float, or ndarray(2,)
    :param Tc: dynamic - motor Coulomb friction [Tc⁺, Tc⁻]
    :type Tc: ndarray(2,)
    :param G: dynamic - gear ratio
    :type G: float

    A subclass of the DHLink class for a prismatic joint that holds all
    information related to a robot link such as kinematics parameters,
    rigid-body inertial parameters, motor and transmission parameters.

    The link transform is

    :math:`\mathbf{T}_{rz}(\theta_i) \cdot \underbrace{\mathbf{T}_{tz}(q_i)}_{\mbox{variable}} \cdot \mathbf{T}_{tx}(a_i) \cdot \mathbf{T}_{rx}(\alpha_i)`

    where :math:`q_i` is the joint variable.

    :references:
        - Robotics, Vision & Control, P. Corke, Springer 2011, Chap 7.

    :seealso: :func:`RevoluteDH`, :func:`DHLink`, :func:`PrismaticMDH`
    """

    def __init__(
            self,
            theta=0.0,
            a=0.0,
            alpha=0.0,
            offset=0.0,
            qlim=np.zeros(2),
            flip=False,
            **kwargs
            ):

        d = 0.0
        sigma = 1
        mdh = False

        super().__init__(
            theta=theta, d=d, a=a, alpha=alpha, sigma=sigma, mdh=mdh,
            offset=offset, qlim=qlim, flip=flip, **kwargs)


class RevoluteMDH(DHLink):
    r"""
    Class for revolute links using modified DH convention

    :param d: kinematic - link offset
    :type d: float
    :param alpha: kinematic - link twist
    :type alpha: float
    :param a: kinematic - link length
    :type a: float
    :param offset: kinematic - joint variable offset
    :type offset: float

    :param qlim: joint variable limits [min, max]
    :type qlim: float ndarray(1,2)
    :param flip: joint moves in opposite direction
    :type flip: bool

    :param m: dynamic - link mass
    :type m: float
    :param r: dynamic - position of COM with respect to link frame
    :type r:  float ndarray(3)
    :param I: dynamic - inertia of link with respect to COM
    :type I: ndarray
    :param Jm: dynamic - motor inertia
    :type Jm: float
    :param B: dynamic - motor viscous friction: B=B⁺=B⁻, [B⁺, B⁻]
    :type B: float, or ndarray(2,)
    :param Tc: dynamic - motor Coulomb friction [Tc⁺, Tc⁻]
    :type Tc: ndarray(2,)
    :param G: dynamic - gear ratio
    :type G: float

    A subclass of the DHLink class for a revolute joint that holds all
    information related to a robot link such as kinematics parameters,
    rigid-body inertial parameters, motor and transmission parameters.

    The link transform is

    :math:`\mathbf{T}_{tx}(a_{i-1}) \cdot \mathbf{T}_{rx}(\alpha_{i-1}) \cdot \underbrace{\mathbf{T}_{rz}(q_i)}_{\mbox{variable}} \cdot \mathbf{T}_{tz}(d_i)`

    where :math:`q_i` is the joint variable.

    :references:
        - Robotics, Vision & Control, P. Corke, Springer 2011, Chap 7.

    :seealso: :func:`PrismaticMDH`, :func:`DHLink`, :func:`RevoluteDH`
    """

    def __init__(
            self,
            d=0.0,
            a=0.0,
            alpha=0.0,
            offset=0.0,
            qlim=np.zeros(2),
            flip=False,
            **kwargs
            ):

        theta = 0.0
        sigma = 0
        mdh = True

        super().__init__(
            d=d, alpha=alpha, theta=theta, a=a, sigma=sigma, mdh=mdh,
            offset=offset, qlim=qlim, flip=flip, **kwargs)


class PrismaticMDH(DHLink):
    r"""
    Class for prismatic link using modified DH convention

    :param theta: kinematic: joint angle
    :type theta: float
    :param d: kinematic - link offset
    :type d: float
    :param alpha: kinematic - link twist
    :type alpha: float
    :param a: kinematic - link length
    :type a: float
    :param offset: kinematic - joint variable offset
    :type offset: float

    :param qlim: joint variable limits [min, max]
    :type qlim: float ndarray(1,2)
    :param flip: joint moves in opposite direction
    :type flip: bool

    :param m: dynamic - link mass
    :type m: float
    :param r: dynamic - position of COM with respect to link frame
    :type r:  float ndarray(3)
    :param I: dynamic - inertia of link with respect to COM
    :type I: ndarray
    :param Jm: dynamic - motor inertia
    :type Jm: float
    :param B: dynamic - motor viscous friction: B=B⁺=B⁻, [B⁺, B⁻]
    :type B: float, or ndarray(2,)
    :param Tc: dynamic - motor Coulomb friction [Tc⁺, Tc⁻]
    :type Tc: ndarray(2,)
    :param G: dynamic - gear ratio
    :type G: float

    A subclass of the DHLink class for a prismatic joint that holds all
    information related to a robot link such as kinematics parameters,
    rigid-body inertial parameters, motor and transmission parameters.

    The link transform is

    :math:`\mathbf{T}_{tx}(a_{i-1}) \cdot \mathbf{T}_{rx}(\alpha_{i-1}) \cdot \mathbf{T}_{rz}(\theta_i) \cdot \underbrace{\mathbf{T}_{tz}(q_i)}_{\mbox{variable}}`

    where :math:`q_i` is the joint variable.

    :references:
        - Robotics, Vision & Control, P. Corke, Springer 2011, Chap 7.

    :seealso: :func:`RevoluteMDH`, :func:`DHLink`, :func:`PrismaticDH`
    """

    def __init__(
            self,
            theta=0.0,
            a=0.0,
            alpha=0.0,
            offset=0.0,
            qlim=np.zeros(2),
            flip=False,
            **kwargs
            ):

        d = 0.0
        sigma = 1
        mdh = True

        super().__init__(
            theta=theta, d=d, a=a, alpha=alpha, sigma=sigma, mdh=mdh,
            offset=offset, qlim=qlim, flip=flip, **kwargs)
