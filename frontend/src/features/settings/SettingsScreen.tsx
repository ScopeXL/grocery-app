import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { ChevronRight, Download, LogOut, Smartphone } from "lucide-react";
import { useEffect, useId, useState, type ReactNode } from "react";

import { api, errorMessage, unwrap } from "../../api/client";
import { qk } from "../../api/keys";
import { liveStatus, type LiveStatus } from "../../lib/events";
import { relativeTime } from "../../lib/format";
import { fetchSession, rememberSignedIn, type Member } from "../../lib/session";
import { useStore } from "../../lib/store";
import { showToast } from "../../lib/toast";
import { Button } from "../../ui/Button";
import { MemberBadge } from "../../ui/MemberBadge";
import { Screen, Section } from "../../ui/Screen";
import { underlined } from "../../ui/styles";
import { CONNECT_RESULTS, type ConnectResult } from "../kroger/account";
import { ChooseStore } from "../stores/ChooseStore";
import { AddPhoneSheet } from "./AddPhoneSheet";
import { KrogerAccountSection } from "./KrogerAccountSection";
import { MemberSheet } from "./MemberSheet";

const LIVE_TEXT: Record<LiveStatus, string> = {
  live: "Live updates: connected",
  connecting: "Live updates: connecting…",
  polling: "Live updates: checking every 30 seconds",
  offline: "Live updates: offline",
  "signed-out": "Live updates: signed out",
};

function Row({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-14 flex-wrap items-center gap-3 border-b border-rule px-4 py-3 last:border-b-0">
      {children}
    </div>
  );
}

function useSession() {
  return useQuery({ queryKey: qk.session(), queryFn: fetchSession });
}

function StoreSettings() {
  const active = useQuery({
    queryKey: qk.activeStore(),
    queryFn: async () => unwrap(await api.GET("/api/stores/active")),
  });
  const [changing, setChanging] = useState(false);
  const store = active.data?.store;
  if (active.isPending) return null;
  return (
    <Section title="Store">
      {store && !changing ? (
        <Row>
          <div className="flex-1">
            <p className="text-body font-semibold">{store.name}</p>
            {store.address_lines.map((line) => (
              <p key={line} className="text-secondary text-ink-soft">
                {line}
              </p>
            ))}
          </div>
          <Button
            variant="secondary"
            onClick={() => {
              setChanging(true);
            }}
          >
            Change store
          </Button>
        </Row>
      ) : null}
      {store && !changing ? (
        <Row>
          <Link
            to="/settings/walking-order"
            className="flex min-h-11 flex-1 items-center justify-between text-body font-semibold text-accent"
          >
            Store walking order
            <ChevronRight aria-hidden="true" />
          </Link>
        </Row>
      ) : (
        <div className="flex flex-col gap-2 p-4">
          <ChooseStore
            onChosen={() => {
              setChanging(false);
              showToast("Store saved");
            }}
          />
          {store ? (
            <Button
              variant="quiet"
              onClick={() => {
                setChanging(false);
              }}
            >
              Keep {store.name}
            </Button>
          ) : null}
        </div>
      )}
    </Section>
  );
}

function ThisPhone() {
  const { data: session } = useSession();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const signOut = useMutation({
    mutationFn: async () => {
      unwrap(await api.POST("/api/auth/logout"));
    },
    onSuccess: async () => {
      rememberSignedIn(false);
      queryClient.setQueryData(qk.session(), null);
      await navigate({ to: "/sign-in" });
    },
    onError: (failure) => showToast(errorMessage(failure)),
  });
  const member = session?.member;
  return (
    <Section title="This phone">
      <Row>
        {member ? <MemberBadge name={member.name} color={member.marker_color} /> : null}
        <span className="flex-1 text-body">
          {member ? `Used by ${member.name}` : "No name picked for this phone yet"}
        </span>
        <Link
          to="/who"
          search={{ from: "settings" }}
          className={`min-h-11 content-center px-2 text-body font-semibold text-accent ${underlined}`}
        >
          Change<span className="sr-only"> who’s using this phone</span>
        </Link>
      </Row>
      <Row>
        <Button
          variant="danger"
          onClick={() => {
            signOut.mutate();
          }}
        >
          <LogOut aria-hidden="true" />
          Sign out of this phone
        </Button>
      </Row>
    </Section>
  );
}

function Household() {
  const queryClient = useQueryClient();
  const { data: session } = useSession();
  const [name, setName] = useState("");
  const [changing, setChanging] = useState<Member | null>(null);
  const nameId = useId();
  const refresh = () => queryClient.invalidateQueries({ queryKey: qk.session() });

  const add = useMutation({
    mutationFn: async (value: string) =>
      unwrap(await api.POST("/api/members", { body: { name: value } })),
    onSuccess: async () => {
      setName("");
      await refresh();
    },
    onError: (failure) => showToast(errorMessage(failure)),
  });

  const restore = useMutation({
    mutationFn: async (id: string) =>
      unwrap(
        await api.POST("/api/members/{member_id}/restore", { params: { path: { member_id: id } } }),
      ),
    onSettled: refresh,
  });

  const remove = useMutation({
    mutationFn: async (id: string) =>
      unwrap(
        await api.POST("/api/members/{member_id}/archive", { params: { path: { member_id: id } } }),
      ),
    onSuccess: async (member) => {
      await refresh();
      showToast(`Removed ${member.name}`, {
        label: "Undo",
        onAction: () => {
          restore.mutate(member.id);
        },
      });
    },
    onError: (failure) => showToast(errorMessage(failure)),
  });

  return (
    <Section title="Household">
      {(session?.members ?? []).map((member) => (
        <Row key={member.id}>
          <MemberBadge name={member.name} color={member.marker_color} />
          <span className="min-w-0 flex-1 text-body font-semibold">{member.name}</span>
          <Button
            variant="quiet"
            className="px-3"
            aria-label={`Change ${member.name}`}
            onClick={() => {
              setChanging(member);
            }}
          >
            Change
          </Button>
        </Row>
      ))}
      <Row>
        <form
          className="flex w-full flex-col gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (name.trim()) add.mutate(name.trim());
          }}
        >
          <label htmlFor={nameId} className="text-body font-semibold">
            Add a person
          </label>
          <div className="flex gap-2">
            <input
              id={nameId}
              value={name}
              maxLength={40}
              onChange={(event) => {
                setName(event.target.value);
              }}
              className="min-h-12 min-w-0 flex-1 rounded-button border-2 border-rule bg-paper px-4 text-body"
            />
            <Button type="submit" variant="secondary" disabled={!name.trim() || add.isPending}>
              Add
            </Button>
          </div>
        </form>
      </Row>
      <MemberSheet
        member={changing}
        onClose={() => {
          setChanging(null);
        }}
        onRemove={(member) => {
          remove.mutate(member.id);
        }}
      />
    </Section>
  );
}

function Devices() {
  const queryClient = useQueryClient();
  const devices = useQuery({
    queryKey: qk.devices(),
    queryFn: async () => unwrap(await api.GET("/api/auth/devices")),
  });
  const others = (devices.data ?? []).filter((device) => !device.is_current).length;
  const [adding, setAdding] = useState(false);
  const signOutOthers = useMutation({
    mutationFn: async () => {
      unwrap(await api.POST("/api/auth/devices/sign-out-others"));
    },
    onSuccess: async () => {
      showToast(others === 1 ? "Signed out 1 other device" : `Signed out ${others} other devices`);
      await queryClient.invalidateQueries({ queryKey: qk.devices() });
    },
    onError: (failure) => showToast(errorMessage(failure)),
  });
  return (
    <Section title="Signed-in devices">
      {(devices.data ?? []).map((device) => (
        <Row key={device.id}>
          <div className="flex-1">
            <p className="text-body font-semibold">
              {device.label}
              {device.is_current ? " (this phone)" : ""}
            </p>
            <p className="text-secondary text-ink-soft">
              {device.member_name ? `${device.member_name}, ` : ""}last used{" "}
              {relativeTime(device.last_seen_at)}
            </p>
          </div>
        </Row>
      ))}
      <Row>
        <Button
          variant="secondary"
          onClick={() => {
            setAdding(true);
          }}
        >
          <Smartphone aria-hidden="true" />
          Add a phone
        </Button>
        {others > 0 ? (
          <Button
            variant="quiet"
            onClick={() => {
              signOutOthers.mutate();
            }}
          >
            Sign out other devices
          </Button>
        ) : null}
      </Row>
      <AddPhoneSheet
        open={adding}
        onClose={() => {
          setAdding(false);
          void queryClient.invalidateQueries({ queryKey: qk.devices() });
        }}
      />
    </Section>
  );
}

function Data() {
  const queryClient = useQueryClient();
  const backups = useQuery({
    queryKey: qk.backups(),
    queryFn: async () => unwrap(await api.GET("/api/admin/backups")),
  });
  const runBackup = useMutation({
    mutationFn: async () => unwrap(await api.POST("/api/admin/backups/run")),
    onSuccess: async () => {
      showToast("Backup saved");
      await queryClient.invalidateQueries({ queryKey: qk.backups() });
    },
    onError: (failure) => showToast(errorMessage(failure)),
  });
  const last = backups.data?.last_success_at;
  return (
    <Section title="Data">
      <Row>
        <a
          href="/api/export"
          download="dinner-bell-export.json"
          className={`inline-flex min-h-11 items-center gap-2 text-body font-semibold text-accent ${underlined}`}
        >
          <Download aria-hidden="true" />
          Export all data
        </a>
      </Row>
      <Row>
        <span className="flex-1 text-body">
          {last ? `Last backup ${relativeTime(last)}` : "No backup yet"}
        </span>
        <Button
          variant="secondary"
          disabled={runBackup.isPending}
          onClick={() => {
            runBackup.mutate();
          }}
        >
          Back up now
        </Button>
      </Row>
    </Section>
  );
}

function Connection() {
  const status = useStore(liveStatus);
  const diagnostics = useQuery({
    queryKey: qk.diagnostics(),
    queryFn: async () => unwrap(await api.GET("/api/admin/diagnostics")),
  });
  const client = diagnostics.data?.client;
  return (
    <Section title="Connection">
      <Row>
        <span className="text-body font-semibold" data-testid="live-status">
          {LIVE_TEXT[status]}
        </span>
      </Row>
      <details className="px-4 py-3">
        <summary className="min-h-11 cursor-pointer content-center text-body font-semibold">
          Details for whoever runs the server
        </summary>
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-secondary">
          <dt className="text-ink-soft">Your address, as seen</dt>
          <dd>{client?.resolved_ip ?? "unknown"}</dd>
          <dt className="text-ink-soft">Forwarded for</dt>
          <dd>{client?.x_forwarded_for ?? "none"}</dd>
          <dt className="text-ink-soft">Forwarded protocol</dt>
          <dd>{client?.x_forwarded_proto ?? "none"}</dd>
          <dt className="text-ink-soft">Trusted proxies set</dt>
          <dd>{client?.trusted_proxies_configured ? "yes" : "no"}</dd>
          <dt className="text-ink-soft">Database revision</dt>
          <dd>{diagnostics.data?.schema_revision ?? "unknown"}</dd>
        </dl>
      </details>
    </Section>
  );
}

function About() {
  const version = useQuery({
    queryKey: ["version"],
    queryFn: async () => unwrap(await api.GET("/api/version")),
  });
  return (
    <Section title="About">
      <Row>
        <span className="flex-1 text-body" data-testid="version">
          Version {version.data?.version ?? __APP_VERSION__}
          {version.data && version.data.version !== __APP_VERSION__
            ? ` (this screen: ${__APP_VERSION__})`
            : ""}
        </span>
        <Link
          to="/about"
          className={`min-h-11 content-center px-2 text-body font-semibold text-accent ${underlined}`}
        >
          About & privacy
        </Link>
      </Row>
    </Section>
  );
}

export function SettingsScreen({ kroger }: { kroger?: ConnectResult | undefined }) {
  const navigate = useNavigate();
  useEffect(() => {
    // Back from Kroger's sign-in page: say how it went, once.
    if (!kroger) return;
    showToast(CONNECT_RESULTS[kroger]);
    void navigate({ to: "/settings", search: {}, replace: true });
  }, [kroger, navigate]);
  return (
    <Screen title="Settings">
      <StoreSettings />
      <ThisPhone />
      <Household />
      <KrogerAccountSection />
      <Devices />
      <Data />
      <Connection />
      <About />
    </Screen>
  );
}
