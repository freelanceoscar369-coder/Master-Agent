/**
 * 404 screen — calm, not broken.
 *
 * Shows the unrecognised path in mono and offers a link home.
 * No decoration, no apology, no stack trace.
 */

import React from 'react';
import { Link, useLocation } from '@/app/router';
import styles from './NotFound.module.css';

export function NotFound(): React.ReactElement {
  const { path } = useLocation();

  return (
    <div className={styles.root}>
      <p className={styles.path}>{path}</p>
      <p className={styles.label}>This path is not in the registry.</p>
      <Link to="/" className={styles.home}>
        Go to Dashboard
      </Link>
    </div>
  );
}
