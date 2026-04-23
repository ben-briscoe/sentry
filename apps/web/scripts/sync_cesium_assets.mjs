import { cpSync, existsSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';


const scriptDir = dirname( fileURLToPath( import.meta.url ) );
const packageRoot = dirname( scriptDir );
const sourceRoot = join( packageRoot, 'node_modules', 'cesium', 'Build', 'Cesium' );
const targetRoot = join( packageRoot, 'public', 'cesium' );
const requiredDirectories = [ 'Workers', 'ThirdParty', 'Assets', 'Widgets' ];


if ( !existsSync( sourceRoot ) ) {
  console.error( `Cesium build directory not found: ${sourceRoot}` );
  process.exit( 1 );
}

mkdirSync( targetRoot, { recursive: true } );

for ( const directoryName of requiredDirectories ) {
  cpSync(
    join( sourceRoot, directoryName ),
    join( targetRoot, directoryName ),
    {
      dereference: true,
      force: true,
      recursive: true,
    },
  );
}

console.log( `Synced Cesium static assets to ${targetRoot}` );

