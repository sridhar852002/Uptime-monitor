import { useCallback, useEffect, useState } from "react";
import { addUrl, deleteUrl, fetchUrls } from "./api";

function formatTime(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

function StatusBadge({ isUp }) {
  if (isUp === null || isUp === undefined) {
    return <span className="badge pending">PENDING</span>;
  }

  return (
    <span className={`badge ${isUp ? "up" : "down"}`}>
      {isUp ? "UP" : "DOWN"}
    </span>
  );
}

export default function App() {
  const [urls, setUrls] = useState([]);
  const [newUrl, setNewUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const loadUrls = useCallback(async () => {
    try {
      const data = await fetchUrls();
      setUrls(data);
      setError("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUrls();
    const interval = setInterval(loadUrls, 10000);
    return () => clearInterval(interval);
  }, [loadUrls]);

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");

    try {
      await addUrl(newUrl.trim());
      setNewUrl("");
      await loadUrls();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id) {
    setError("");
    try {
      await deleteUrl(id);
      await loadUrls();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page">
      <header>
        <h1>Uptime Monitor</h1>
        <p>Track URL availability and latest response times.</p>
      </header>

      <section className="card">
        <h2>Add URL</h2>
        <form onSubmit={handleSubmit} className="form-row">
          <input
            type="url"
            placeholder="https://example.com"
            value={newUrl}
            onChange={(event) => setNewUrl(event.target.value)}
            required
          />
          <button type="submit" disabled={submitting}>
            {submitting ? "Adding..." : "Monitor URL"}
          </button>
        </form>
      </section>

      {error && <div className="alert">{error}</div>}

      <section className="card">
        <div className="section-header">
          <h2>Monitored URLs</h2>
          <span className="hint">Auto-refreshes every 10 seconds</span>
        </div>

        {loading ? (
          <p>Loading...</p>
        ) : urls.length === 0 ? (
          <p className="empty">No URLs yet. Add one to start monitoring.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>URL</th>
                  <th>Status</th>
                  <th>Response Time</th>
                  <th>Last Checked</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {urls.map((item) => (
                  <tr key={item.id}>
                    <td className="url-cell">{item.url}</td>
                    <td>
                      <StatusBadge isUp={item.latest_check?.is_up} />
                    </td>
                    <td>
                      {item.latest_check?.response_time_ms != null
                        ? `${item.latest_check.response_time_ms} ms`
                        : "—"}
                    </td>
                    <td>{formatTime(item.latest_check?.checked_at)}</td>
                    <td>
                      <button
                        className="danger"
                        onClick={() => handleDelete(item.id)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
