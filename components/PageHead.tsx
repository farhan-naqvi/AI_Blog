export function PageHead({ kicker, title, description }: { kicker: string; title: string; description: string }) {
  return <header className="page-head"><div className="shell"><span className="kicker">{kicker}</span><h1>{title}</h1><p>{description}</p></div></header>;
}
