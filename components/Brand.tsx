import Link from "next/link";

export function Brand() {
  return (
    <Link href="/" className="brand" aria-label="SignalWatch AI home">
      <span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>
      <span>SignalWatch <b>AI</b></span>
    </Link>
  );
}
