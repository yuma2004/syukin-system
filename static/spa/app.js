const {useCallback, useEffect, useState} = React;

const API_BASE = "/api";

function parseError(payload) {
  if (payload && typeof payload === "object" && payload.error && payload.error.message) {
    return String(payload.error.message);
  }
  return "Request failed";
}

async function apiRequest(path, options = {}) {
  const {method = "GET", body} = options;
  const csrfToken = window.__spaCsrfToken;

  const headers = {
    Accept: "application/json",
  };

  const fetchOptions = {
    method,
    headers,
    credentials: "same-origin",
  };

  if (body !== undefined && body !== null) {
    const payload = {
      ...body,
      ...(csrfToken ? {csrf_token: csrfToken} : {}),
    };
    headers["Content-Type"] = "application/json";
    fetchOptions.body = JSON.stringify(payload);
  }

  const response = await fetch(`${API_BASE}${path}`, fetchOptions);
  const payload = await response.json().catch(() => null);
  if (!response.ok || (payload && payload.ok === false)) {
    const message = parseError(payload);
    throw new Error(message || `Request failed (${response.status})`);
  }

  return payload ? payload.data : null;
}

function StatusBadge({statusText, statusTone = "idle"}) {
  return <span className={`statusBadge ${statusTone}`}>{statusText}</span>;
}

function ClockPanel({dashboard, onClockAction, isAdmin, error}) {
  const canClockIn = !dashboard?.open_shift;
  const canStartBreak = dashboard?.open_shift && !dashboard?.open_break;
  const canEndBreak = !!dashboard?.open_break;
  const canClockOut = !!dashboard?.open_shift;

  const buttons = [];
  if (canClockIn) {
    buttons.push(
      <button key="clock-in" onClick={() => onClockAction("/clock/in")}>
        Clock In
      </button>
    );
  }
  if (canStartBreak) {
    buttons.push(
      <button key="break-start" onClick={() => onClockAction("/break/start")}>
        Start Break
      </button>
    );
  }
  if (canEndBreak) {
    buttons.push(
      <button key="break-end" onClick={() => onClockAction("/break/end")}>
        End Break
      </button>
    );
  }
  if (canClockOut) {
    buttons.push(
      <button key="clock-out" onClick={() => onClockAction("/clock/out")}>
        Clock Out
      </button>
    );
  }

  return (
    <section className="card">
      <h2>Clock Controls</h2>
      <p>Use this panel to clock in/out and manage breaks.</p>
      <div className="actions">{buttons}</div>
      {isAdmin ? <p className="muted">Administrative routes remain available in template views.</p> : null}
      {error ? <p className="error">{error}</p> : null}
    </section>
  );
}

function RecentRows({rows}) {
  if (!rows.length) {
    return <p>No recent shifts yet.</p>;
  }

  return (
    <ul className="recentList">
      {rows.map((row) => (
        <li key={row.id}>
          <span>{row.id}</span>
          <span>{row.date_label || "-"}</span>
          <span>{row.time_label || "-"}</span>
          <span>{row.status_label || "-"}</span>
          <span>{row.worked_label || "-"}</span>
          <span>{row.break_label || "-"}</span>
        </li>
      ))}
    </ul>
  );
}

function DashboardView({session, dashboard, setError, error, onClockAction, onLogout}) {
  return (
    <div className="shell">
      <header className="topBar">
        <div>
          <h1>{dashboard?.greeting_text || `Hello, ${session.user?.name || session.user?.username || "User"}`}</h1>
          <p className="muted">Welcome to React Attendance dashboard.</p>
        </div>
        <button className="danger" onClick={onLogout}>Logout</button>
      </header>

      <section className="grid">
        <article className="card">
          <h2>Current Status</h2>
          <div className="statusLine">
            <StatusBadge statusText={dashboard?.status_text || "Idle"} statusTone={dashboard?.status_tone || "idle"} />
            <span>Now: {dashboard?.current_worked_label || "00:00:00"}</span>
          </div>
          <p className="muted">Timezone: {dashboard?.dashboard_timezone || "local"}</p>
        </article>

        <ClockPanel
          dashboard={dashboard}
          onClockAction={onClockAction}
          isAdmin={session.user?.is_admin}
          error={error}
          onError={setError}
        />
      </section>

      <section className="card">
        <h2>Recent Shifts</h2>
        <RecentRows rows={dashboard?.recent_rows || []} />
      </section>

      <section className="card">
        <h2>Month Progress</h2>
        <p>Workday: {dashboard?.month_stats?.workday_label || "-"}</p>
        <p>Total worked: {dashboard?.month_stats?.worked_hms || "00:00"}</p>
        <p>Overtime: {dashboard?.month_stats?.overtime_hms || "00:00"}</p>
      </section>
    </div>
  );
}

function LoginForm({onLogin, error}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const submit = async (event) => {
    event.preventDefault();
    onLogin({username, password});
  };

  return (
    <div className="authCard">
      <h1>Sign in</h1>
      <form onSubmit={submit}>
        <label>
          Username
          <input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
          />
        </label>
        <label>
          Password
          <input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            autoComplete="current-password"
          />
        </label>
        <button type="submit">Login</button>
        {error ? <p className="error">{error}</p> : null}
      </form>
    </div>
  );
}

function App() {
  const [state, setState] = useState({
    session: null,
    dashboard: null,
    loading: true,
    error: "",
    mode: "login",
  });

  const refreshSession = useCallback(async () => {
    const session = await apiRequest("/session");
    window.__spaCsrfToken = session.csrf_token;

    setState((current) => ({
      ...current,
      session,
      mode: session.authenticated ? "dashboard" : "login",
      error: "",
    }));

    if (session.authenticated) {
      const dashboard = await apiRequest("/dashboard");
      setState((current) => ({
        ...current,
        dashboard,
        session,
      }));
    }
  }, []);

  const load = useCallback(async () => {
    try {
      setState((current) => ({...current, loading: true, error: ""}));
      await refreshSession();
    } catch (error) {
      setState((current) => ({...current, error: error.message, loading: false}));
    } finally {
      setState((current) => ({...current, loading: false}));
    }
  }, [refreshSession]);

  useEffect(() => {
    load();
  }, [load]);

  const handleLogin = async ({username, password}) => {
    try {
      setState((current) => ({...current, loading: true, error: ""}));
      await apiRequest("/login", {
        method: "POST",
        body: {username, password, remember_me: false},
      });
      await refreshSession();
    } catch (error) {
      setState((current) => ({...current, error: error.message}));
    } finally {
      setState((current) => ({...current, loading: false}));
    }
  };

  const handleClockAction = async (path) => {
    try {
      setState((current) => ({...current, loading: true, error: ""}));
      await apiRequest(path, {method: "POST"});
      const dashboard = await apiRequest("/dashboard");
      setState((current) => ({...current, dashboard, error: ""}));
    } catch (error) {
      setState((current) => ({...current, error: error.message}));
    } finally {
      setState((current) => ({...current, loading: false}));
    }
  };

  const handleLogout = async () => {
    try {
      setState((current) => ({...current, loading: true, error: ""}));
      await apiRequest("/logout", {method: "POST"});
    } catch (error) {
      setState((current) => ({...current, error: error.message}));
      return;
    }

    window.__spaCsrfToken = "";
    setState((current) => ({
      session: {...current.session, authenticated: false, user: null},
      dashboard: null,
      loading: false,
      error: "",
      mode: "login",
    }));
  };

  if (state.loading && !state.session) {
    return <div className="loading">Loading...</div>;
  }

  if (!state.session || state.mode === "login") {
    return <LoginForm onLogin={handleLogin} error={state.error} />;
  }

  return (
    <DashboardView
      session={state.session}
      dashboard={state.dashboard}
      onClockAction={handleClockAction}
      onLogout={handleLogout}
      error={state.error}
      setError={(message) => setState((current) => ({...current, error: message}))}
    />
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
