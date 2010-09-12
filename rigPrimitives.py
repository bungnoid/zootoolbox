'''
To create a new rig primitive, create a class and author the rigging code in the
_build
'''

from skeletonBuilderCore import *
from rigPrim_base import __author__, RigPart, WorldPart, RigSubPart, PrimaryRigPart
from rigPrim_bipedLimbs import IkFkArm, IkFkLeg
from rigPrim_curves import *
from rigPrim_hands import Hand
from rigPrim_heads import Head
from rigPrim_misc import ControlHierarchy, WeaponControlHierarchy
from rigPrim_quadrupeds import QuadrupedIkFkLeg
from rigPrim_root import Root
from rigPrim_spines import FkSpine


#now populate a dictionary that associates the skeleton part classes with a list of valid rigging classes - this dict can be used to lookup a list of methods to expose to a user in a UI
_rigMethodDict = {}
for cls in RigPart.GetSubclasses():
	try:
		assoc = cls.SKELETON_PRIM_ASSOC
	except AttributeError: continue

	if assoc is None:
		continue

	for partCls in assoc:
		try:
			_rigMethodDict[ partCls ].append( (cls.PRIORITY, cls) )
		except KeyError:
			_rigMethodDict[ partCls ] = [ (cls.PRIORITY, cls) ]

for partCls, rigTypes in _rigMethodDict.iteritems():
	rigTypes.sort()
	rigTypes = [ rigType for priority, rigType in rigTypes ]
	partCls.RigTypes = rigTypes


#end
