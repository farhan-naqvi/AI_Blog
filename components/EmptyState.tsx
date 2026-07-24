export function EmptyState({ title = "No verified intelligence yet", detail = "Collectors are ready. Published items will appear here after primary-source verification." }) {
  return <div className="empty-state"><span className="pulse-ring" /><h3>{title}</h3><p>{detail}</p></div>;
}
