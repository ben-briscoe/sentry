import {
  Cartesian3,
  Ellipsoid,
  Math as CesiumMath,
  Matrix3,
  Matrix4,
  Quaternion,
  Transforms,
} from 'cesium';


export function resolveVelocityAlignedQuaternion(
  currentPosition: Cartesian3,
  previousPosition: Cartesian3 | null,
  nextPosition: Cartesian3 | null,
  rollDeg: number,
): Quaternion | null {
  const velocityVector = nextPosition
    ? Cartesian3.subtract( nextPosition, currentPosition, new Cartesian3() )
    : previousPosition
      ? Cartesian3.subtract( currentPosition, previousPosition, new Cartesian3() )
      : null;

  if ( !velocityVector || Cartesian3.magnitudeSquared( velocityVector ) <= 1e-6 ) {
    return null;
  }

  const forwardAxis = Cartesian3.normalize( velocityVector, new Cartesian3() );
  const localUpAxis = Ellipsoid.WGS84.geodeticSurfaceNormal( currentPosition, new Cartesian3() );
  let rightAxis = Cartesian3.cross( localUpAxis, forwardAxis, new Cartesian3() );

  if ( Cartesian3.magnitudeSquared( rightAxis ) <= 1e-6 ) {
    const enuFrame = Transforms.eastNorthUpToFixedFrame( currentPosition );
    const localNorthAxis = Matrix4.multiplyByPointAsVector( enuFrame, Cartesian3.UNIT_Y, new Cartesian3() );
    rightAxis = Cartesian3.cross( localNorthAxis, forwardAxis, new Cartesian3() );
  }

  if ( Cartesian3.magnitudeSquared( rightAxis ) <= 1e-6 ) {
    rightAxis = Cartesian3.cross( Cartesian3.UNIT_Z, forwardAxis, new Cartesian3() );
  }

  rightAxis = Cartesian3.normalize( rightAxis, rightAxis );
  const upAxis = Cartesian3.normalize( Cartesian3.cross( forwardAxis, rightAxis, new Cartesian3() ), new Cartesian3() );
  const motionRotation = Matrix3.fromColumnMajorArray( [
    forwardAxis.x,
    forwardAxis.y,
    forwardAxis.z,
    rightAxis.x,
    rightAxis.y,
    rightAxis.z,
    upAxis.x,
    upAxis.y,
    upAxis.z,
  ] );
  let quaternion = Quaternion.fromRotationMatrix( motionRotation );

  if ( Math.abs( rollDeg ) > 1e-6 ) {
    const rollQuaternion = Quaternion.fromAxisAngle( Cartesian3.UNIT_X, CesiumMath.toRadians( -rollDeg ) );
    quaternion = Quaternion.multiply( quaternion, rollQuaternion, new Quaternion() );
  }

  return quaternion;
}


export function resolveCylinderQuaternionBetweenPoints(
  centerPosition: Cartesian3,
  startPosition: Cartesian3,
  endPosition: Cartesian3,
): Quaternion | null {
  const baseQuaternion = resolveVelocityAlignedQuaternion(
    centerPosition,
    startPosition,
    endPosition,
    0.0,
  );

  if ( !baseQuaternion ) {
    return null;
  }

  const zAxisToForwardAxis = Quaternion.fromAxisAngle(
    Cartesian3.UNIT_Y,
    CesiumMath.toRadians( 90.0 ),
  );
  return Quaternion.multiply( baseQuaternion, zAxisToForwardAxis, new Quaternion() );
}
