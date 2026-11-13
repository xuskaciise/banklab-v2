"use client";

import { useState } from "react";
import { toast } from "sonner";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCsvConfirm, useCsvPreview } from "@/lib/lab";
import type { CsvResult } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import {
  ErrorMsg,
  PageHeader,
  Table,
  Td,
  Th,
} from "@/components/lab/common";
import { cn } from "@/lib/utils";

const MAX_ROWS = 500;

function ResultTable({ result }: { result: CsvResult }) {
  return (
    <Table>
      <thead>
        <tr>
          <Th>Line</Th>
          <Th>Student ID</Th>
          <Th>Full name</Th>
          <Th>Phone</Th>
          <Th>Result</Th>
        </tr>
      </thead>
      <tbody>
        {result.rows.map((r) => (
          <tr
            key={r.line}
            className={cn(r.action === "error" && "bg-fin-danger-bg")}
          >
            <Td className="text-text-muted">{r.line}</Td>
            <Td>{r.username}</Td>
            <Td>{r.full_name}</Td>
            <Td>{r.phone}</Td>
            <Td>
              {r.action === "error" ? (
                <span className="text-fin-danger">{r.error}</span>
              ) : (
                <span className="text-fin-success-dark">
                  {r.action === "create" ? "Will create and enroll" : "Will enroll"}
                </span>
              )}
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

export default function ImportPage() {
  const { id } = useParams<{ id: string }>();
  const preview = useCsvPreview(id);
  const confirm = useCsvConfirm(id);
  const [text, setText] = useState("");
  const [clientError, setClientError] = useState<string | null>(null);

  const lineCount = text.split(/\r?\n/).filter((l) => l.trim()).length;
  const result = confirm.data ?? preview.data;
  const done = confirm.isSuccess;

  async function onFile(ev: React.ChangeEvent<HTMLInputElement>) {
    const f = ev.target.files?.[0];
    if (!f) return;
    setText(await f.text());
    preview.reset();
    confirm.reset();
  }

  function runPreview() {
    setClientError(null);
    if (!text.trim()) return setClientError("Paste CSV text or choose a file first");
    if (lineCount - 1 > MAX_ROWS)
      return setClientError(`A file can have at most ${MAX_ROWS} rows`);
    confirm.reset();
    preview.mutate(text);
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Import students"
        subtitle="Columns: username, full_name, phone (header row required, max 500 rows)."
      />
      {!done && (
        <div className="space-y-3 rounded-xl border border-border bg-card p-5 shadow-xs">
          <input
            type="file"
            accept=".csv,text/csv,text/plain"
            onChange={onFile}
            aria-label="CSV file"
            className="text-sm text-text-body"
          />
          <textarea
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              preview.reset();
            }}
            rows={8}
            placeholder={"username,full_name,phone\nS1001,Amina Yusuf,615123456"}
            aria-label="CSV text"
            className="w-full rounded-md border border-border bg-card p-3 font-mono text-sm text-text-body outline-none focus-visible:ring-2 focus-visible:ring-bank-accent"
          />
          {clientError && (
            <p role="alert" className="text-sm text-fin-danger">
              {clientError}
            </p>
          )}
          <ErrorMsg error={preview.error} />
          <Button onClick={runPreview} disabled={preview.isPending}>
            {preview.isPending ? "Checking…" : "Preview"}
          </Button>
        </div>
      )}

      {result && (
        <div className="space-y-3">
          {done ? (
            <p
              role="status"
              className="rounded-md bg-fin-success-bg px-3 py-2 text-sm text-fin-success-dark"
            >
              Import finished: {result.ok_count} imported, {result.error_count}{" "}
              rejected.
            </p>
          ) : (
            <p className="text-sm text-text-body">
              {result.ok_count} row(s) ready,{" "}
              <span className={result.error_count ? "text-fin-danger" : ""}>
                {result.error_count} with errors
              </span>
              . Rows with errors are skipped on confirm.
            </p>
          )}
          <ResultTable result={result} />
          <ErrorMsg error={confirm.error} />
          {done ? (
            <Link href={`/instructor/classes/${id}`}>
              <Button>Back to students</Button>
            </Link>
          ) : (
            <Button
              disabled={confirm.isPending || result.ok_count === 0}
              onClick={() =>
                confirm.mutate(text, {
                  onSuccess: (r) =>
                    toast.success(`Import finished: ${r.ok_count} imported`),
                })
              }
            >
              {confirm.isPending
                ? "Importing…"
                : `Confirm import (${result.ok_count})`}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
