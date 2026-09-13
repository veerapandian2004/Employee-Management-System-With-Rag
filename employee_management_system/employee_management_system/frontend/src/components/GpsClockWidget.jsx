import { useState, useEffect, useRef } from "react";
import {
  MapPin,
  Clock,
  LogIn,
  LogOut,
  CheckCircle2,
  AlertCircle,
  Building2,
  Navigation,
  RefreshCw,
  ShieldCheck,
  Radio,
} from "lucide-react";
import { Card, CardContent } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import {
  apiClockIn,
  apiClockOut,
  apiPingLocation,
  apiGetMyAttendanceStatus,
} from "../services/apiService";

export function GpsClockWidget({ onAttendanceUpdated }) {
  const [statusData, setStatusData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [gpsFix, setGpsFix] = useState(null); // { lat, lon, accuracy }
  const [gpsStage, setGpsStage] = useState(null); // 'requesting' | 'verifying' | null
  const [liveDuration, setLiveDuration] = useState(0);

  const timerRef = useRef(null);
  const heartbeatRef = useRef(null);

  // Load initial status
  const fetchStatus = async () => {
    try {
      setIsLoading(true);
      const data = await apiGetMyAttendanceStatus();
      setStatusData(data);
      if (data?.working_duration_seconds) {
        setLiveDuration(data.working_duration_seconds);
      } else {
        setLiveDuration(0);
      }
    } catch (err) {
      console.warn("Failed to fetch attendance status:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  // Real-time ticking stopwatch when "Working"
  useEffect(() => {
    if (statusData?.is_clocked_in) {
      timerRef.current = setInterval(() => {
        setLiveDuration((prev) => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [statusData?.is_clocked_in]);

  // Periodic location-based geofence monitoring while clocked in
  useEffect(() => {
    if (statusData?.is_clocked_in) {
      const checkGeofence = async () => {
        if (!navigator.geolocation) return;
        navigator.geolocation.getCurrentPosition(
          async (pos) => {
            try {
              const res = await apiPingLocation({
                latitude: pos.coords.latitude,
                longitude: pos.coords.longitude,
                accuracy: pos.coords.accuracy,
              });
              if (res?.auto_clocked_out) {
                setErrorMessage(
                  `⚠️ Automatic Clock-Out: You left the permitted office geofence (${res.distance ? Math.round(res.distance) + "m" : "outside"}). Reason: ${res.reason}.`
                );
                await fetchStatus();
                if (onAttendanceUpdated) onAttendanceUpdated();
              }
            } catch (err) {
              console.warn("Geofence heartbeat ping error:", err);
            }
          },
          (err) => {
            console.warn("Geofence geolocation warning:", err);
          },
          { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 }
        );
      };

      // Check geofence every 60 seconds
      heartbeatRef.current = setInterval(checkGeofence, 60000);
    } else {
      if (heartbeatRef.current) clearInterval(heartbeatRef.current);
    }
    return () => {
      if (heartbeatRef.current) clearInterval(heartbeatRef.current);
    };
  }, [statusData?.is_clocked_in]);

  const formatDuration = (seconds) => {
    if (!seconds || seconds <= 0) return "00h 00m 00s";
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${String(hrs).padStart(2, "0")}h ${String(mins).padStart(2, "0")}m ${String(secs).padStart(2, "0")}s`;
  };

  const formatTimeDisplay = (timeStr) => {
    if (!timeStr) return "—";
    try {
      const d = new Date(timeStr);
      if (isNaN(d.getTime())) {
        return timeStr.slice(0, 8);
      }
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch {
      return timeStr;
    }
  };

  // Acquire Geolocation from browser
  const getBrowserCoordinates = () => {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        return reject(new Error("Geolocation is not supported by your browser."));
      }
      setGpsStage("requesting");
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const { latitude, longitude, accuracy } = pos.coords;
          setGpsFix({ latitude, longitude, accuracy });
          setGpsStage("verifying");
          resolve({ latitude, longitude, accuracy });
        },
        (err) => {
          let msg = "Failed to acquire GPS location.";
          if (err.code === 1) {
            msg = "Location permission denied. Please allow browser location access to clock in/out.";
          } else if (err.code === 2) {
            msg = "GPS location unavailable. Please ensure location services are enabled on your device.";
          } else if (err.code === 3) {
            msg = "GPS request timed out. Please retry in an open area with good reception.";
          }
          reject(new Error(msg));
        },
        {
          enableHighAccuracy: true,
          timeout: 15000,
          maximumAge: 0,
        }
      );
    });
  };

  const handleClockIn = async () => {
    setErrorMessage(null);
    setSuccessMessage(null);
    setActionLoading(true);

    try {
      const coords = await getBrowserCoordinates();
      // Server-side security: send ONLY latitude, longitude, accuracy
      const res = await apiClockIn({
        latitude: coords.latitude,
        longitude: coords.longitude,
        accuracy: coords.accuracy,
      });

      const dist = res?.distance !== undefined ? `${res.distance}m from office` : "Office Radius Verified";
      setSuccessMessage(`Clocked IN successfully! (${dist})`);
      await fetchStatus();
      if (onAttendanceUpdated) onAttendanceUpdated();
    } catch (err) {
      setErrorMessage(err.message || "Failed to clock in.");
    } finally {
      setActionLoading(false);
      setGpsStage(null);
    }
  };

  const handleClockOut = async () => {
    setErrorMessage(null);
    setSuccessMessage(null);
    setActionLoading(true);

    try {
      const coords = await getBrowserCoordinates();
      // Server-side security: send ONLY latitude, longitude, accuracy
      const res = await apiClockOut({
        latitude: coords.latitude,
        longitude: coords.longitude,
        accuracy: coords.accuracy,
      });

      const dist = res?.distance !== undefined ? `${res.distance}m from office` : "Office Radius Verified";
      setSuccessMessage(`Clocked OUT successfully! (${dist})`);
      await fetchStatus();
      if (onAttendanceUpdated) onAttendanceUpdated();
    } catch (err) {
      setErrorMessage(err.message || "Failed to clock out.");
    } finally {
      setActionLoading(false);
      setGpsStage(null);
    }
  };

  const isClockedIn = Boolean(statusData?.is_clocked_in);
  const currentStatus = statusData?.current_status || (isClockedIn ? "Working" : "Not Clocked In");
  const office = statusData?.office;
  const shift = statusData?.today_shift;

  return (
    <Card className="overflow-hidden border-2 border-indigo-100 dark:border-indigo-950/60 shadow-lg bg-gradient-to-br from-white via-slate-50/50 to-indigo-50/30 dark:from-slate-900 dark:via-slate-900 dark:to-indigo-950/20">
      {/* Top Status Strip */}
      <div className="bg-slate-900 dark:bg-slate-950 px-6 py-3 text-white flex flex-wrap items-center justify-between gap-3 border-b border-slate-800">
        <div className="flex items-center space-x-2">
          <ShieldCheck className="h-4 w-4 text-emerald-400" />
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
            Secure GPS Attendance Verification
          </span>
        </div>
        <div className="flex items-center space-x-2 text-xs">
          {office ? (
            <span className="flex items-center space-x-1 text-slate-300">
              <Building2 className="h-3.5 w-3.5 text-indigo-400" />
              <span className="font-medium text-white">{office.office_name}</span>
              <span className="text-slate-400">({office.allowed_radius}m radius)</span>
            </span>
          ) : (
            <span className="text-slate-400">Office location resolving...</span>
          )}
        </div>
      </div>

      <CardContent className="p-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-center">
          {/* Col 1: Shift & Status */}
          <div className="space-y-3 lg:border-r border-slate-200 dark:border-slate-800 lg:pr-6">
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                Today's Shift
              </p>
              <h4 className="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center space-x-2 mt-0.5">
                <Clock className="h-4 w-4 text-indigo-600 dark:text-indigo-400 shrink-0" />
                <span>{shift ? `${shift.shift_name} (${shift.start_time} – ${shift.end_time})` : "Standard Day Shift (09:00 – 17:00)"}</span>
              </h4>
            </div>

            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                Current Status
              </p>
              <div className="flex items-center space-x-2 mt-1">
                {isClockedIn ? (
                  <Badge className="bg-emerald-600 text-white font-semibold px-3 py-1 text-xs shadow-sm animate-pulse flex items-center space-x-1.5">
                    <Radio className="h-3 w-3" />
                    <span>Working</span>
                  </Badge>
                ) : currentStatus === "Clocked Out" ? (
                  <Badge variant="secondary" className="bg-slate-200 text-slate-800 dark:bg-slate-800 dark:text-slate-200 font-semibold px-3 py-1 text-xs">
                    Clocked Out
                  </Badge>
                ) : (
                  <Badge variant="outline" className="border-slate-300 text-slate-600 dark:border-slate-700 dark:text-slate-400 font-medium px-3 py-1 text-xs">
                    Not Clocked In
                  </Badge>
                )}
                {statusData?.auto_clocked_out && statusData?.clock_out_reason && (
                  <Badge variant="outline" className="border-amber-400 text-amber-800 dark:border-amber-600 dark:text-amber-300 font-semibold px-2 py-0.5 text-[11px] bg-amber-50 dark:bg-amber-950/40">
                    Auto: {statusData.clock_out_reason}
                  </Badge>
                )}
              </div>
            </div>
          </div>

          {/* Col 2: Live Timer & In/Out Timestamps */}
          <div className="space-y-3 lg:border-r border-slate-200 dark:border-slate-800 lg:pr-6">
            <div>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                Working Duration
              </p>
              <div className="text-2xl sm:text-3xl font-extrabold font-mono tracking-tight text-slate-900 dark:text-slate-100 mt-0.5">
                {formatDuration(liveDuration)}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="bg-slate-100 dark:bg-slate-800/60 p-2.5 rounded-lg">
                <span className="text-slate-500 dark:text-slate-400 block font-medium">Clock IN</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">
                  {formatTimeDisplay(statusData?.clock_in_time)}
                </span>
              </div>
              <div className="bg-slate-100 dark:bg-slate-800/60 p-2.5 rounded-lg">
                <span className="text-slate-500 dark:text-slate-400 block font-medium">Clock OUT</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">
                  {formatTimeDisplay(statusData?.clock_out_time)}
                </span>
              </div>
            </div>
          </div>

          {/* Col 3: GPS Actions */}
          <div className="flex flex-col justify-center space-y-3">
            {isClockedIn ? (
              <Button
                onClick={handleClockOut}
                disabled={actionLoading}
                className="w-full h-12 bg-amber-600 hover:bg-amber-700 text-white font-bold text-sm shadow-md transition-all active:scale-[0.98]"
              >
                {actionLoading ? (
                  <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <LogOut className="mr-2 h-4 w-4" />
                )}
                {actionLoading
                  ? gpsStage === "requesting"
                    ? "Acquiring GPS Fix..."
                    : "Verifying Office Radius..."
                  : "CLOCK OUT"}
              </Button>
            ) : (
              <Button
                onClick={handleClockIn}
                disabled={actionLoading}
                className="w-full h-12 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-sm shadow-md transition-all active:scale-[0.98]"
              >
                {actionLoading ? (
                  <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <LogIn className="mr-2 h-4 w-4" />
                )}
                {actionLoading
                  ? gpsStage === "requesting"
                    ? "Acquiring GPS Fix..."
                    : "Verifying Office Radius..."
                  : "CLOCK IN"}
              </Button>
            )}

            <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400 px-1">
              <span className="flex items-center space-x-1">
                <MapPin className="h-3 w-3 text-indigo-500" />
                <span>
                  {gpsFix
                    ? `GPS Accuracy: ±${Math.round(gpsFix.accuracy)}m`
                    : "GPS Location Required"}
                </span>
              </span>
              <button
                type="button"
                onClick={fetchStatus}
                disabled={isLoading || actionLoading}
                className="hover:text-indigo-600 dark:hover:text-indigo-400 flex items-center space-x-1 transition-colors"
                title="Refresh Status"
              >
                <RefreshCw className={`h-3 w-3 ${isLoading ? "animate-spin" : ""}`} />
                <span>Sync</span>
              </button>
            </div>
          </div>
        </div>

        {/* Feedback Banners */}
        {errorMessage && (
          <div className="mt-4 p-3 rounded-xl bg-rose-50 border border-rose-200 dark:bg-rose-950/40 dark:border-rose-900 text-rose-800 dark:text-rose-300 text-xs flex items-start space-x-2 animate-in fade-in">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-600 dark:text-rose-400" />
            <div className="flex-1">
              <p className="font-semibold">Attendance Verification Rejected</p>
              <p className="mt-0.5">{errorMessage}</p>
            </div>
          </div>
        )}

        {successMessage && (
          <div className="mt-4 p-3 rounded-xl bg-emerald-50 border border-emerald-200 dark:bg-emerald-950/40 dark:border-emerald-900 text-emerald-800 dark:text-emerald-300 text-xs flex items-center space-x-2 animate-in fade-in">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
            <span className="font-medium">{successMessage}</span>
          </div>
        )}

        {statusData?.auto_clocked_out && statusData?.clock_out_reason && (
          <div className="mt-4 p-3 rounded-xl bg-amber-50 border border-amber-200 dark:bg-amber-950/40 dark:border-amber-900 text-amber-800 dark:text-amber-300 text-xs flex items-center space-x-2 animate-in fade-in">
            <AlertCircle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
            <div>
              <span className="font-semibold">Automatic Clock-Out:</span> Session closed due to{" "}
              <span className="font-bold underline">{statusData.clock_out_reason}</span>
              {statusData.auto_clock_out_time ? ` at ${formatTimeDisplay(statusData.auto_clock_out_time)}` : ""}.
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

