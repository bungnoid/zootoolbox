from pymel.core import *

import vectors
import re

Vector = vectors.Vector

class Colour(Vector):
	NAMED_PRESETS = { "active": (0.26, 1, 0.64),
	                  "black": (0, 0, 0),
	                  "white": (1, 1, 1),
	                  "grey": (.5, .5, .5),
	                  "lightgrey": (.7, .7, .7),
	                  "darkgrey": (.25, .25, .25),
	                  "red": (1, 0, 0),
	                  "lightred": (1, .5, 1),
	                  "peach": (1, .5, .5),
	                  "darkred": (.6, 0, 0),
	                  "orange": (1., .5, 0),
	                  "lightorange": (1, .7, .1),
	                  "darkorange": (.7, .25, 0),
	                  "yellow": (1, 1, 0),
	                  "lightyellow": (1, 1, .5),
	                  "darkyellow": (.8,.8,0.),
	                  "green": (0, 1, 0),
	                  "lightgreen": (.4, 1, .2),
	                  "darkgreen": (0, .5, 0),
	                  "blue": (0, 0, 1),
	                  "lightblue": (.4, .55, 1),
	                  "darkblue": (0, 0, .4),
	                  "purple": (.7, 0, 1),
	                  "lightpurple": (.8, .5, 1),
	                  "darkpurple": (.375, 0, .5),
	                  "brown": (.57, .49, .39),
	                  "lightbrown": (.76, .64, .5),
	                  "darkbrown": (.37, .28, .17) }

	NAMED_PRESETS[ 'highlight' ] = NAMED_PRESETS[ 'active' ]
	NAMED_PRESETS[ 'pink' ] = NAMED_PRESETS[ 'lightred' ]

	DEFAULT_COLOUR = NAMED_PRESETS[ 'black' ]
	DEFAULT_ALPHA = 0.7  #this is maya transparency, so alpha=0 is opaque, alpha=1 is transparent

	INDEX_NAMES = 'rgba'
	_EQ_TOLERANCE = 0.1

	_NUM_RE = re.compile( '^[0-9. ]+' )


	def __eq__( self, other, tolerance=_EQ_TOLERANCE ):
		return Vector.__eq__( self, other, tolerance )
	def __ne__( self, other, tolerance=_EQ_TOLERANCE ):
		return Vector.__ne__( self, other, tolerance )
	def __init__( self, colour ):
		'''
		colour can be a combination:
		name alpha  ->  darkred 0.5
		name
		r g b a  ->  1 0 0 0.2
		if r, g, b or a are missing, they're assumed to be 0
		a 4 float, RGBA array is returned
		'''
		if isinstance( colour, basestring ):
			alpha = self.DEFAULT_ALPHA
			toks = colour.lower().split( ' ' )[ :4 ]

			if len( toks ) > 1:
				if toks[ -1 ].isdigit():
					alpha = float( toks[ -1 ] )

			clr = [0,0,0,alpha]
			for n, c in enumerate( self.DEFAULT_COLOUR[ :4 ] ):
				clr[ n ] = c

			clr[ 3 ] = alpha

			if not toks[ 0 ].isdigit():
				try:
					clr = list( self.NAMED_PRESETS[ toks[ 0 ] ] )[ :3 ]
					clr.append( alpha )
				except KeyError: pass
			else:
				for n, t in enumerate( toks ):
					try: clr[ n ] = float( t )
					except ValueError: continue
		else:
			clr = colour

		Vector.__init__( self, clr )
	def darken( self, factor ):
		'''
		returns a colour vector that has been darkened by the appropriate ratio.
		this is basically just a multiply, but the alpha is unaffected
		'''
		darkened = self * factor
		darkened[ 3 ] = self[ 3 ]

		return darkened
	def lighten( self, factor ):
		toWhiteDelta = Colour( (1,1,1,0) ) - self
		toWhiteDelta = toWhiteDelta * factor
		lightened = self + toWhiteDelta
		lightened[ 3 ] = self[ 3 ]

		return lightened
	@classmethod
	def ColourToName( cls, theColour ):
		'''
		given an arbitrary colour, will return the most appropriate name as
		defined in the NAMED_PRESETS class dict
		'''
		if not isinstance( theColour, Colour ):
			theColour = Colour( theColour )

		theColour = Vector( theColour[ :3 ] )  #make sure its a 3 vector
		matches = []
		for name, colour in cls.NAMED_PRESETS.iteritems():
			colour = Vector( colour )
			diff = (colour - theColour).mag
			matches.append( (diff, name) )

		matches.sort()

		return matches[ 0 ][ 1 ]

Color = Colour  #for spelling n00bs


def setShaderColour( shader, colour ):
	if not isinstance( colour, Colour ):
		colour = Colour( colour )

	shader.outColor.set( *colour )
	if colour[ 3 ]:
		a = colour[ 3 ]
		shader.outTransparency.set( a, a, a )


def setObjShader( obj, shader ):
	SG = shader.outColor.listConnections( s=False, type='shadingEngine' )[ 0 ]
	shapes = obj.listRelatives( pa=True, s=True )

	for shape in shapes:
		if shape.nodeType() == 'nurbsCurve': continue
		sets( SG, e=True, forceElement=shape )


def getObjShader( obj ):
	'''
	returns the shader currently assigned to the given object
	'''
	shapes = listRelatives( obj, s=True )
	if not shapes: return None

	cons = listConnections( shapes, s=False, type='shadingEngine' )
	for c in cons:
		shaders = listConnections( c.surfaceShader, d=False )
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

	shaders = ls( type='surfaceShader' )

	for shader in shaders:
		thisColour = list( shader.outColor.get() )
		alpha = shader.outTransparency.get()[ 0 ]

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
	shader = shadingNode( 'surfaceShader', asShader=True )
	shader.rename( name )

	SG = sets( renderable=True, noSurfaceShader=True, empty=True )
	SG.rename( '%s_SG' % name )

	connectAttr( shader.outColor, SG.surfaceShader, f=True )
	shader.outColor.set( *colour[ :3 ] )

	a = colour[ 3 ]
	shader.outTransparency.set( a, a, a )

	shadingConnection( SG.surfaceShader, e=True, cs=False )

	return shader


#end
