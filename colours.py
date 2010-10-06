from maya.cmds import *

import maya.cmds as cmd
import vectors
import re

Vector = vectors.Vector
Colour = Color = vectors.Colour


def setShaderColour( shader, colour ):
	if not isinstance( colour, Colour ):
		colour = Colour( colour )

	setAttr( '%s.outColor' % shader, *colour )
	if colour[ 3 ]:
		a = colour[ 3 ]
		setAttr( '%s.outTransparency' % shader, a, a, a )


def setObjShader( obj, shader ):
	SG = listConnections( '%s.outColor' % shader, s=False, type='shadingEngine' )[ 0 ]
	shapes = listRelatives( obj, pa=True, s=True ) or []

	for shape in shapes:
		if nodeType( shape ) == 'nurbsCurve': continue
		sets( shape, e=True, forceElement=SG )


def getObjShader( obj ):
	'''
	returns the shader currently assigned to the given object
	'''
	shapes = listRelatives( obj, s=True ) or []
	if not shapes: return None

	cons = listConnections( shapes, s=False, type='shadingEngine' ) or []
	for c in cons:
		shaders = listConnections( c.surfaceShader, d=False ) or []
		if shaders: return shaders[ 0 ]


def getShader( colour, forceCreate=True ):
	'''
	given a colour, this proc will either return an existing shader with that colour
	or it will create a new shader (if forceCreate is true) if an existing one isn't
	found

	NOTE - this proc will look for a shader that has a similar colour to the one
	specified - so the colour may not always be totally accurate if a shader exists
	with a similar colour - the colour/alpha threshold is 0.05
	'''
	if not isinstance( colour, Colour ):
		colour = Colour( colour )

	shaders = ls( type='surfaceShader' ) or []

	for shader in shaders:
		thisColour = list( getAttr( '%s.outColor' % shader )[ 0 ] )
		alpha = getAttr( '%s.outTransparency' % shader )[ 0 ][ 0 ]

		thisColour.append( alpha )
		thisColour = Colour( thisColour )

		if thisColour == colour: return shader

	if forceCreate:
		return createShader( colour )

	return None


def createShader( colour ):
	'''
	creates a shader of a given colour - always creates a new shader
	'''
	name = 'rigShader_%s' % Colour.ColourToName( colour )
	shader = shadingNode( 'surfaceShader', name=name, asShader=True )

	SG = sets( name='%s_SG' % name, renderable=True, noSurfaceShader=True, empty=True )

	connectAttr( '%s.outColor' % shader, '%s.surfaceShader' % SG, f=True )
	setAttr( '%s.outColor' % shader, *colour[ :3 ] )

	a = colour[ 3 ]
	setAttr( '%s.outTransparency' % shader, a, a, a )

	shadingConnection( '%s.surfaceShader' % SG, e=True, cs=False )

	return shader


#end
