import { useCallback, useEffect, useRef, useState, type CSSProperties, type PointerEvent as ReactPointerEvent } from 'react';


const DEFAULT_TELEMETRY_WIDTH_PX = 360;
const MIN_TELEMETRY_WIDTH_PX = 320;
const MAX_TELEMETRY_WIDTH_PX = 560;

type TelemetryRailLayoutStyle = CSSProperties & {
  '--telemetry-width'?: string;
};

type TelemetryRailLayoutController = {
  beginResize: ( event: ReactPointerEvent<HTMLButtonElement> ) => void;
  collapsed: boolean;
  layoutStyle: TelemetryRailLayoutStyle;
  toggleCollapsed: () => void;
};


function clampTelemetryWidth( requestedWidthPx: number ): number {
  if ( typeof window === 'undefined' ) {
    return Math.max( MIN_TELEMETRY_WIDTH_PX, Math.min( requestedWidthPx, MAX_TELEMETRY_WIDTH_PX ) );
  }

  const viewportLimitedMax = Math.max( MIN_TELEMETRY_WIDTH_PX, Math.min( MAX_TELEMETRY_WIDTH_PX, window.innerWidth * 0.42 ) );
  return Math.max( MIN_TELEMETRY_WIDTH_PX, Math.min( requestedWidthPx, viewportLimitedMax ) );
}


export function useTelemetryRailLayout(): TelemetryRailLayoutController {
  const [ widthPx, setWidthPx ] = useState( DEFAULT_TELEMETRY_WIDTH_PX );
  const [ collapsed, setCollapsed ] = useState( false );
  const cleanupResizeRef = useRef<( () => void ) | null>( null );

  useEffect( () => {
    return () => {
      cleanupResizeRef.current?.();
    };
  }, [] );

  const beginResize = useCallback( ( event: ReactPointerEvent<HTMLButtonElement> ) => {
    if ( collapsed ) {
      return;
    }

    event.preventDefault();

    const startX = event.clientX;
    const startWidthPx = widthPx;
    const previousCursor = document.body.style.cursor;
    const previousUserSelect = document.body.style.userSelect;

    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const onPointerMove = ( moveEvent: PointerEvent ) => {
      const nextWidthPx = clampTelemetryWidth( startWidthPx - ( moveEvent.clientX - startX ) );
      setWidthPx( nextWidthPx );
    };

    const onPointerUp = () => {
      window.removeEventListener( 'pointermove', onPointerMove );
      window.removeEventListener( 'pointerup', onPointerUp );
      document.body.style.cursor = previousCursor;
      document.body.style.userSelect = previousUserSelect;
      cleanupResizeRef.current = null;
    };

    cleanupResizeRef.current = onPointerUp;
    window.addEventListener( 'pointermove', onPointerMove );
    window.addEventListener( 'pointerup', onPointerUp );
  }, [ collapsed, widthPx ] );

  const toggleCollapsed = useCallback( () => {
    setCollapsed( ( current ) => !current );
  }, [] );

  return {
    beginResize,
    collapsed,
    layoutStyle: {
      '--telemetry-width': `${widthPx}px`,
    },
    toggleCollapsed,
  };
}
