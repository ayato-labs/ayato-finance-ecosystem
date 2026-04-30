'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function Navigation() {
  const pathname = usePathname();

  const links = [
    { name: 'Dashboard', href: '/' },
    { name: 'Evaluation', href: '/analysis' },
    { name: 'History', href: '/transactions' },
  ];

  return (
    <nav className="nav-container">
      <div style={{ display: 'flex', alignItems: 'center', gap: '3rem' }}>
        <h1 className="gradient-text" style={{ fontSize: '1.5rem', fontWeight: 800, letterSpacing: '-0.02em' }}>
          AYATO ASSET
        </h1>
        <div style={{ display: 'flex', gap: '1.5rem' }}>
          {links.map((link) => {
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={isActive ? 'nav-link active' : 'nav-link'}
                style={{ 
                  fontSize: '0.875rem', 
                  fontWeight: isActive ? 600 : 400,
                  transition: 'all 0.2s ease'
                }}
              >
                {link.name}
              </Link>
            );
          })}
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <span style={{ 
          color: 'rgba(255,255,255,0.4)', 
          fontSize: '0.75rem', 
          background: 'rgba(255,255,255,0.05)',
          padding: '4px 12px',
          borderRadius: '100px',
          border: '1px solid rgba(255,255,255,0.1)'
        }}>
          Alpha V1.1
        </span>
      </div>
    </nav>
  );
}
