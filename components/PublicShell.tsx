import Link from "next/link";
import { PublicHeader } from "./PublicHeader";

export function PublicShell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <PublicHeader />
      <main>{children}</main>
      <footer>
        <div className="shell footer-row">
          <span>SignalWatch AI · evidence before velocity</span>
          <span><Link href="/sources">Source policy</Link> · <Link href="/owner-login">Owner</Link></span>
        </div>
      </footer>
    </>
  );
}
