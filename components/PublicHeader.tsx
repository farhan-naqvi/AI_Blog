import Link from "next/link";
import { Brand } from "./Brand";

const links = [
  ["Latest", "/latest"],
  ["Daily", "/briefing"],
  ["Weekly", "/weekly"],
  ["Trends", "/trends"],
  ["Sources", "/sources"],
];

export function PublicHeader() {
  return (
    <header className="topbar">
      <div className="shell nav-row">
        <Brand />
        <nav aria-label="Primary navigation">
          {links.map(([label, href]) => <Link key={href} href={href}>{label}</Link>)}
        </nav>
        <Link href="/search" className="search-link" aria-label="Search intelligence">⌕ <span>Search</span></Link>
      </div>
    </header>
  );
}
