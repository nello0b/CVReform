export function SiteHeader({ expanded = false }: { expanded?: boolean }) {
  return (
    <header className={`site-header${expanded ? " site-header--result" : ""}`}>
      <a className="brand" href="/" aria-label="CVReform home">
        <img src="/favicon.svg" alt="" />
        <span>CVReform</span>
      </a>
      <span className="header-note">Editable CVs, without starting over</span>
    </header>
  );
}
